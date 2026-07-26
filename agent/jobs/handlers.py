"""Concrete maintenance job handlers used by the privileged agent."""

import asyncio
import base64
import hashlib
import json
import os
import shutil
import socket
import sqlite3
import subprocess
import tarfile
import tempfile
from datetime import datetime, timedelta, timezone
from pathlib import Path
from typing import Any, Dict, Iterable, Optional

import psutil
from cryptography.hazmat.primitives.ciphers import Cipher, algorithms, modes

from .runner import Job


BACKUP_MAGIC = b"PCBACKUP1"
DEFAULT_DATABASES = {
    "control_db": Path("/var/lib/pi-control/control.db"),
    "telemetry_db": Path("/var/lib/pi-control/telemetry.db"),
}


def _sha256(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as source:
        for chunk in iter(lambda: source.read(1024 * 1024), b""):
            digest.update(chunk)
    return digest.hexdigest()


def _sqlite_snapshot(source_path: Path, target_path: Path) -> None:
    target_path.parent.mkdir(parents=True, exist_ok=True)
    source = sqlite3.connect(f"file:{source_path}?mode=ro", uri=True, timeout=5)
    try:
        destination = sqlite3.connect(target_path)
        try:
            source.backup(destination)
        finally:
            destination.close()
    finally:
        source.close()


def _sqlite_integrity(path: Path) -> str:
    connection = sqlite3.connect(f"file:{path}?mode=ro", uri=True, timeout=5)
    try:
        row = connection.execute("PRAGMA quick_check").fetchone()
        return str(row[0]) if row else "no result"
    finally:
        connection.close()


def _load_key(path: Path, create: bool = False) -> bytes:
    if not path.exists():
        if not create:
            raise FileNotFoundError(f"Backup encryption key not found: {path}")
        path.parent.mkdir(parents=True, exist_ok=True)
        key = os.urandom(32)
        path.write_text(base64.urlsafe_b64encode(key).decode("ascii"), encoding="ascii")
        path.chmod(0o600)
        return key
    raw = path.read_text(encoding="ascii").strip().encode("ascii")
    key = base64.urlsafe_b64decode(raw)
    if len(key) != 32:
        raise ValueError("Backup encryption key must decode to 32 bytes")
    return key


def _encrypt(source: Path, destination: Path, key: bytes) -> None:
    nonce = os.urandom(12)
    encryptor = Cipher(algorithms.AES(key), modes.GCM(nonce)).encryptor()
    with source.open("rb") as src, destination.open("wb") as dst:
        dst.write(BACKUP_MAGIC)
        dst.write(nonce)
        for chunk in iter(lambda: src.read(1024 * 1024), b""):
            dst.write(encryptor.update(chunk))
        dst.write(encryptor.finalize())
        dst.write(encryptor.tag)
    destination.chmod(0o600)


def _decrypt(source: Path, destination: Path, key: bytes) -> None:
    size = source.stat().st_size
    minimum = len(BACKUP_MAGIC) + 12 + 16
    if size < minimum:
        raise ValueError("Backup file is truncated")
    with source.open("rb") as src:
        if src.read(len(BACKUP_MAGIC)) != BACKUP_MAGIC:
            raise ValueError("Unsupported backup format")
        nonce = src.read(12)
        src.seek(-16, os.SEEK_END)
        tag = src.read(16)
        encrypted_size = size - minimum
        src.seek(len(BACKUP_MAGIC) + 12)
        decryptor = Cipher(algorithms.AES(key), modes.GCM(nonce, tag)).decryptor()
        with destination.open("wb") as dst:
            remaining = encrypted_size
            while remaining:
                chunk = src.read(min(1024 * 1024, remaining))
                if not chunk:
                    raise ValueError("Backup payload ended unexpectedly")
                remaining -= len(chunk)
                dst.write(decryptor.update(chunk))
            dst.write(decryptor.finalize())


def _safe_extract(archive: tarfile.TarFile, target: Path) -> None:
    target = target.resolve()
    for member in archive.getmembers():
        member_path = (target / member.name).resolve()
        if not member_path.is_relative_to(target):
            raise ValueError(f"Unsafe archive member: {member.name}")
        if member.issym() or member.islnk() or member.isdev():
            raise ValueError(f"Unsupported archive member: {member.name}")
    archive.extractall(target, filter="data")


def _copy_tree_filtered(source: Path, target: Path, excludes: Iterable[str]) -> None:
    excluded = set(excludes)

    def ignore(_directory: str, names: list[str]) -> set[str]:
        return {name for name in names if name in excluded}

    shutil.copytree(source, target, symlinks=False, ignore=ignore)


class BackupBundle:
    def __init__(self, config: dict):
        jobs = config.get("jobs", {})
        self.backup_dir = Path(jobs.get("backup_dir", "/opt/pi-control/backups"))
        self.key_file = Path(jobs.get("backup_key_file", "/etc/pi-control/backup_encryption.key"))
        self.install_dir = Path(jobs.get("install_dir", "/opt/pi-control"))
        self.config_dir = Path(jobs.get("config_dir", "/etc/pi-control"))

    def create(self, components: Iterable[str], trigger: str = "job") -> Dict[str, Any]:
        requested = set(components)
        allowed = {"control_db", "telemetry_db", "app_config", "release"}
        unknown = requested - allowed
        if unknown:
            raise ValueError(f"Unsupported backup components: {', '.join(sorted(unknown))}")
        stamp = datetime.now().strftime("%Y-%m-%d_%H%M%S")
        self.backup_dir.mkdir(parents=True, exist_ok=True)
        output = self.backup_dir / f"pi-control_backup_{stamp}.tar.gz.enc"
        with tempfile.TemporaryDirectory(prefix="pi-control-bundle-") as temp_name:
            temp = Path(temp_name)
            payload = temp / "pi-control-backup"
            payload.mkdir()
            files: list[Dict[str, Any]] = []

            for component, source in DEFAULT_DATABASES.items():
                if component not in requested or not source.exists():
                    continue
                target = payload / "databases" / source.name
                _sqlite_snapshot(source, target)
                files.append(self._entry(component, target, payload))

            if "app_config" in requested and self.config_dir.exists():
                target = payload / "config"
                _copy_tree_filtered(
                    self.config_dir,
                    target,
                    {self.key_file.name, "jwt_secret", "caddy-internal-ca"},
                )
                files.extend(self._tree_entries("app_config", target, payload))

            if "release" in requested and self.install_dir.exists():
                source = self.install_dir / "current"
                if not source.exists():
                    source = self.install_dir
                target = payload / "release"
                _copy_tree_filtered(
                    source,
                    target,
                    {".git", "venv", "node_modules", "dist", "backups", "releases", "ReadMePhotos"},
                )
                files.extend(self._tree_entries("release", target, payload))

            manifest = {
                "format_version": 2,
                "app": "pi-control",
                "created_at": datetime.now(timezone.utc).isoformat(),
                "hostname": socket.gethostname(),
                "trigger": trigger,
                "components": sorted(requested),
                "files": files,
            }
            manifest_path = payload / "manifest.json"
            manifest_path.write_text(json.dumps(manifest, indent=2), encoding="utf-8")
            archive_path = temp / "bundle.tar.gz"
            with tarfile.open(archive_path, "w:gz") as archive:
                archive.add(payload, arcname="pi-control-backup", recursive=True)
            _encrypt(archive_path, output, _load_key(self.key_file, create=True))

        return {
            "status": "completed_local_only",
            "filename": output.name,
            "path": str(output),
            "size_bytes": output.stat().st_size,
            "checksum": _sha256(output),
            "manifest": manifest,
        }

    def inspect(self, source: Path, staging: Optional[Path] = None) -> Dict[str, Any]:
        source = source.resolve()
        if not source.is_file():
            raise FileNotFoundError(f"Backup not found: {source}")
        owned_temp = tempfile.TemporaryDirectory(prefix="pi-control-inspect-") if staging is None else None
        target = staging or Path(owned_temp.name)
        target.mkdir(parents=True, exist_ok=True)
        decrypted = target / "bundle.tar.gz"
        _decrypt(source, decrypted, _load_key(self.key_file))
        with tarfile.open(decrypted, "r:gz") as archive:
            _safe_extract(archive, target)
        decrypted.unlink(missing_ok=True)
        payload = target / "pi-control-backup"
        manifest_path = payload / "manifest.json"
        manifest = json.loads(manifest_path.read_text(encoding="utf-8"))
        if manifest.get("app") != "pi-control":
            raise ValueError("Backup belongs to a different application")

        errors: list[str] = []
        if not manifest.get("components"):
            legacy_components = []
            if (payload / "databases" / "control.db").exists():
                legacy_components.append("control_db")
            if (payload / "databases" / "telemetry.db").exists():
                legacy_components.append("telemetry_db")
            if (payload / "config").exists():
                legacy_components.append("app_config")
            if (payload / "release").exists():
                legacy_components.append("release")
            manifest["components"] = legacy_components
        for entry in manifest.get("files", []):
            file_path = payload / entry["path"]
            if not file_path.is_file():
                errors.append(f"Missing: {entry['path']}")
            elif _sha256(file_path) != entry["sha256"]:
                errors.append(f"Checksum mismatch: {entry['path']}")
        for db_file in (payload / "databases").glob("*.db") if (payload / "databases").exists() else []:
            result = _sqlite_integrity(db_file)
            if result != "ok":
                errors.append(f"SQLite integrity failed for {db_file.name}: {result}")
        response = {
            "valid": not errors,
            "errors": errors,
            "checksum": _sha256(source),
            "size_bytes": source.stat().st_size,
            "manifest": manifest,
            "components": manifest.get("components", []),
        }
        if staging is not None:
            response["payload_path"] = str(payload)
        if owned_temp:
            owned_temp.cleanup()
        return response

    def export_key(self) -> str:
        """Return the portable recovery key without logging it."""
        return base64.urlsafe_b64encode(_load_key(self.key_file)).decode("ascii")

    def import_key(self, encoded_key: str, replace: bool = False) -> None:
        try:
            decoded = base64.urlsafe_b64decode(encoded_key.strip().encode("ascii"))
        except Exception as exc:
            raise ValueError("Invalid recovery key encoding") from exc
        if len(decoded) != 32:
            raise ValueError("Recovery key must contain 32 bytes")
        if self.key_file.exists() and not replace:
            raise FileExistsError("A recovery key already exists")
        self.key_file.parent.mkdir(parents=True, exist_ok=True)
        temporary = self.key_file.with_suffix(".tmp")
        temporary.write_text(base64.urlsafe_b64encode(decoded).decode("ascii"), encoding="ascii")
        temporary.chmod(0o600)
        os.replace(temporary, self.key_file)

    @staticmethod
    def _entry(component: str, path: Path, root: Path) -> Dict[str, Any]:
        return {
            "component": component,
            "path": path.relative_to(root).as_posix(),
            "size_bytes": path.stat().st_size,
            "sha256": _sha256(path),
        }

    def _tree_entries(self, component: str, tree: Path, root: Path) -> list[Dict[str, Any]]:
        return [self._entry(component, path, root) for path in tree.rglob("*") if path.is_file()]


class BackupJobHandler:
    def __init__(self, config: dict):
        self.bundle = BackupBundle(config)

    async def precheck(self, job: Job) -> Dict[str, Any]:
        free = shutil.disk_usage(self.bundle.backup_dir.parent).free
        return {"passed": free >= 256 * 1024 * 1024, "reason": "At least 256 MiB free space is required"}

    async def execute(self, job: Job) -> Dict[str, Any]:
        components = job.config.get("components") or ["control_db", "telemetry_db", "app_config", "release"]
        return await asyncio.to_thread(self.bundle.create, components, "job")

    async def verify(self, job: Job, result: Dict[str, Any]) -> Dict[str, Any]:
        inspected = await asyncio.to_thread(self.bundle.inspect, Path(result["path"]))
        return {"passed": inspected["valid"], "reason": "; ".join(inspected["errors"])}


class RestoreJobHandler:
    def __init__(self, config: dict):
        self.bundle = BackupBundle(config)
        jobs = config.get("jobs", {})
        self.restore_root = Path(jobs.get("restore_dir", "/var/lib/pi-control/restore"))
        self.jobs_db = Path(jobs.get("db_path", "/var/lib/pi-control/jobs.db"))

    async def precheck(self, job: Job) -> Dict[str, Any]:
        source = self._source(job)
        try:
            inspected = await asyncio.to_thread(self.bundle.inspect, source)
            return {"passed": inspected["valid"], "reason": "; ".join(inspected["errors"])}
        except Exception as exc:
            return {"passed": False, "reason": str(exc)}

    async def snapshot(self, job: Job) -> Dict[str, Any]:
        if job.config.get("dry_run", True):
            return {"dry_run": True}
        result = await asyncio.to_thread(
            self.bundle.create,
            ["control_db", "telemetry_db", "app_config"],
            "pre_restore",
        )
        return {"backup_path": result["path"], "checksum": result["checksum"]}

    async def execute(self, job: Job) -> Dict[str, Any]:
        source = self._source(job)
        selected = set(job.config.get("components") or [])
        if job.config.get("dry_run", True):
            inspected = await asyncio.to_thread(self.bundle.inspect, source)
            if selected:
                inspected["selected_components"] = sorted(selected)
            return inspected
        if not job.config.get("confirmed"):
            raise ValueError("Restore requires explicit confirmation")

        staging = self.restore_root / job.id
        shutil.rmtree(staging, ignore_errors=True)
        inspected = await asyncio.to_thread(self.bundle.inspect, source, staging)
        available = set(inspected["components"])
        selected = selected or available
        if not selected <= available:
            raise ValueError(f"Backup does not contain: {', '.join(sorted(selected - available))}")
        plan = {
            "job_id": job.id,
            "jobs_db": str(self.jobs_db),
            "payload_path": inspected["payload_path"],
            "components": sorted(selected),
            "rollback_backup": job.checkpoint.get("backup_path") if job.checkpoint else None,
            "install_dir": str(self.bundle.install_dir),
            "config_dir": str(self.bundle.config_dir),
        }
        plan_path = staging / "restore-plan.json"
        plan_path.write_text(json.dumps(plan), encoding="utf-8")
        helper = self.bundle.install_dir / "current" / "scripts" / "restore_helper.py"
        if not helper.exists():
            helper = self.bundle.install_dir / "scripts" / "restore_helper.py"
        command = [
            "systemd-run", "--quiet", "--collect", f"--unit=pi-control-restore-{job.id}",
            "/usr/bin/python3", str(helper), str(plan_path),
        ]
        process = await asyncio.create_subprocess_exec(*command)
        if await process.wait() != 0:
            raise RuntimeError("Failed to start restore maintenance unit")
        return {"handoff": True, "maintenance_unit": f"pi-control-restore-{job.id}.service"}

    async def verify(self, job: Job, result: Dict[str, Any]) -> Dict[str, Any]:
        return {"passed": True}

    async def rollback(self, job: Job, snapshot: Dict[str, Any]) -> Dict[str, Any]:
        return {"deferred_to_maintenance_helper": bool(snapshot.get("backup_path"))}

    def _source(self, job: Job) -> Path:
        raw = str(job.config.get("backup_path") or "")
        if not raw:
            raise ValueError("backup_path is required")
        source = Path(raw).resolve()
        backup_root = self.bundle.backup_dir.resolve()
        if not source.is_relative_to(backup_root):
            raise ValueError("Restore source must be inside the configured backup directory")
        return source


class HealthCheckJobHandler:
    async def precheck(self, job: Job) -> Dict[str, Any]:
        return {"passed": True}

    async def execute(self, job: Job) -> Dict[str, Any]:
        checks: list[Dict[str, Any]] = []
        for service in ("pi-agent", "pi-control", "caddy", "NetworkManager"):
            process = await asyncio.create_subprocess_exec(
                "systemctl", "is-active", service,
                stdout=asyncio.subprocess.PIPE, stderr=asyncio.subprocess.PIPE,
            )
            stdout, _ = await process.communicate()
            state = stdout.decode().strip() or "unknown"
            checks.append({"name": f"service:{service}", "passed": state == "active", "value": state})
        for name, path in DEFAULT_DATABASES.items():
            try:
                result = await asyncio.to_thread(_sqlite_integrity, path)
                checks.append({"name": name, "passed": result == "ok", "value": result})
            except Exception as exc:
                checks.append({"name": name, "passed": False, "value": str(exc)})
        disk = psutil.disk_usage("/")
        checks.append({"name": "disk", "passed": disk.percent < 90, "value": disk.percent})
        temperatures = psutil.sensors_temperatures()
        current = [entry.current for values in temperatures.values() for entry in values if entry.current]
        if current:
            checks.append({"name": "temperature", "passed": max(current) < 80, "value": max(current)})
        return {
            "passed": all(check["passed"] for check in checks),
            "checks": checks,
            "checked_at": datetime.now(timezone.utc).isoformat(),
        }

    async def verify(self, job: Job, result: Dict[str, Any]) -> Dict[str, Any]:
        return {"passed": True}


class CleanupJobHandler:
    def __init__(self, config: dict):
        jobs = config.get("jobs", {})
        self.backup_dir = Path(jobs.get("backup_dir", "/opt/pi-control/backups"))

    async def precheck(self, job: Job) -> Dict[str, Any]:
        retention = int(job.config.get("retention_days", 30))
        return {"passed": 1 <= retention <= 3650, "reason": "retention_days must be between 1 and 3650"}

    async def execute(self, job: Job) -> Dict[str, Any]:
        retention = int(job.config.get("retention_days", 30))
        cutoff = datetime.now() - timedelta(days=retention)
        candidates = []
        if self.backup_dir.exists():
            for path in self.backup_dir.iterdir():
                if not path.is_file() or not path.name.startswith(("daily_", "archive_", "manual_")):
                    continue
                if datetime.fromtimestamp(path.stat().st_mtime) < cutoff:
                    candidates.append({"path": str(path), "size_bytes": path.stat().st_size})
        dangling = await self._docker_dangling_images()
        dry_run = job.config.get("dry_run", True)
        deleted = []
        if not dry_run:
            if not job.config.get("confirmed"):
                raise ValueError("Cleanup apply requires explicit confirmation")
            for item in candidates:
                Path(item["path"]).unlink(missing_ok=True)
                deleted.append(item["path"])
            if job.config.get("prune_unused_images", False):
                process = await asyncio.create_subprocess_exec("docker", "image", "prune", "-f")
                if await process.wait() != 0:
                    raise RuntimeError("Docker image cleanup failed")
        return {
            "dry_run": dry_run,
            "candidates": candidates,
            "candidate_bytes": sum(item["size_bytes"] for item in candidates),
            "dangling_images": dangling,
            "deleted": deleted,
        }

    async def verify(self, job: Job, result: Dict[str, Any]) -> Dict[str, Any]:
        return {"passed": True}

    async def _docker_dangling_images(self) -> list[str]:
        try:
            process = await asyncio.create_subprocess_exec(
                "docker", "images", "--filter", "dangling=true", "--format", "{{.ID}} {{.Size}}",
                stdout=asyncio.subprocess.PIPE, stderr=asyncio.subprocess.PIPE,
            )
            stdout, _ = await process.communicate()
            return stdout.decode().splitlines() if process.returncode == 0 else []
        except FileNotFoundError:
            return []


class UpdateJobHandler:
    def __init__(self, config: dict):
        jobs = config.get("jobs", {})
        self.install_dir = Path(jobs.get("install_dir", "/opt/pi-control"))
        self.releases_dir = self.install_dir / "releases"
        self.repository = jobs.get("repository", "https://github.com/BGirginn/rasp_pi_webUI.git")
        self.jobs_db = Path(jobs.get("db_path", "/var/lib/pi-control/jobs.db"))
        self.install_user = str(jobs.get("install_user", "fou4"))

    async def precheck(self, job: Job) -> Dict[str, Any]:
        scope = job.config.get("scope", "application")
        if scope not in {"application", "security"}:
            return {"passed": False, "reason": "Update scope must be application or security"}
        return {
            "passed": shutil.disk_usage(self.install_dir).free >= 1024 * 1024 * 1024,
            "reason": "At least 1 GiB free space is required to stage an update",
        }

    async def snapshot(self, job: Job) -> Dict[str, Any]:
        current = self.install_dir / "current"
        return {"current_release": str(current.resolve()) if current.is_symlink() else None}

    async def execute(self, job: Job) -> Dict[str, Any]:
        if job.config.get("scope", "application") == "security":
            return await self._security_update(job)
        self.releases_dir.mkdir(parents=True, exist_ok=True)
        branch = str(job.config.get("branch", "main"))
        if not branch.replace("-", "").replace("_", "").isalnum():
            raise ValueError("Invalid update branch")
        with tempfile.TemporaryDirectory(prefix="pi-control-update-") as temp_name:
            temp = Path(temp_name)
            await self._run("git", "clone", "--depth", "1", "--branch", branch, self.repository, str(temp))
            commit = (await self._capture("git", "-C", str(temp), "rev-parse", "HEAD")).strip()
            if job.config.get("approved_commit") and job.config["approved_commit"] != commit:
                raise ValueError("Remote commit changed after approval")
            if job.config.get("dry_run", True):
                return {"dry_run": True, "commit": commit, "branch": branch}
            if not job.config.get("confirmed"):
                raise ValueError("Update requires explicit confirmation")
            release = self.releases_dir / commit
            if not release.exists():
                shutil.copytree(temp, release, ignore=shutil.ignore_patterns(".git", "node_modules", "venv", "dist"))
                shutil.chown(release, user=self.install_user, group=self.install_user)
                for child in release.rglob("*"):
                    try:
                        shutil.chown(child, user=self.install_user, group=self.install_user)
                    except FileNotFoundError:
                        pass
                await self._run("runuser", "-u", self.install_user, "--", "/usr/bin/python3", "-m", "venv", str(release / "venv"))
                await self._run("runuser", "-u", self.install_user, "--", str(release / "venv" / "bin" / "pip"), "install", "-r", str(release / "panel" / "api" / "requirements.txt"))
                await self._run("runuser", "-u", self.install_user, "--", "npm", "ci", "--prefix", str(release / "panel" / "ui"), "--no-audit")
                await self._run("runuser", "-u", self.install_user, "--", "npm", "--prefix", str(release / "panel" / "ui"), "run", "build")
                shutil.rmtree(release / "panel" / "ui" / "node_modules", ignore_errors=True)
            current = self.install_dir / "current"
            if not current.is_symlink():
                raise RuntimeError("Atomic release layout is not initialized; run the installer upgrade first")
            plan = {
                "job_id": job.id,
                "jobs_db": str(self.jobs_db),
                "current": str(current),
                "release": str(release),
            }
            plan_path = release / "update-plan.json"
            plan_path.write_text(json.dumps(plan), encoding="utf-8")
            helper = current / "scripts" / "update_helper.py"
            process = await asyncio.create_subprocess_exec(
                "systemd-run", "--quiet", "--collect", f"--unit=pi-control-update-{job.id}",
                "/usr/bin/python3", str(helper), str(plan_path),
            )
            if await process.wait() != 0:
                raise RuntimeError("Failed to start update maintenance unit")
            return {"staged": True, "handoff": True, "commit": commit, "release_path": str(release)}

    async def verify(self, job: Job, result: Dict[str, Any]) -> Dict[str, Any]:
        if result.get("scope") == "security":
            return {"passed": True}
        if result.get("dry_run"):
            return {"passed": True}
        release = Path(result["release_path"])
        return {"passed": (release / "install.sh").is_file(), "reason": "Staged release is incomplete"}

    async def rollback(self, job: Job, snapshot: Dict[str, Any]) -> Dict[str, Any]:
        if job.config.get("scope", "application") == "security":
            raise RuntimeError("Security package rollback requires an explicit package recovery plan")
        return {"current_release": snapshot.get("current_release")}

    async def _run(self, *command: str) -> None:
        process = await asyncio.create_subprocess_exec(
            *command, stdout=asyncio.subprocess.PIPE, stderr=asyncio.subprocess.PIPE
        )
        _, stderr = await process.communicate()
        if process.returncode != 0:
            raise RuntimeError(stderr.decode().strip() or f"Command failed: {command[0]}")

    async def _capture(self, *command: str) -> str:
        process = await asyncio.create_subprocess_exec(
            *command, stdout=asyncio.subprocess.PIPE, stderr=asyncio.subprocess.PIPE
        )
        stdout, stderr = await process.communicate()
        if process.returncode != 0:
            raise RuntimeError(stderr.decode().strip() or f"Command failed: {command[0]}")
        return stdout.decode()

    async def _security_update(self, job: Job) -> Dict[str, Any]:
        command = ["unattended-upgrade", "--dry-run", "--debug"]
        if not shutil.which(command[0]):
            raise RuntimeError("unattended-upgrades is not installed")
        if job.config.get("dry_run", True):
            output = await self._capture(*command)
            return {"scope": "security", "dry_run": True, "output": output[-12000:], "rebooted": False}
        if not job.config.get("confirmed"):
            raise ValueError("Security updates require explicit confirmation")
        output = await self._capture("unattended-upgrade", "--debug")
        reboot_required = Path("/var/run/reboot-required").exists()
        return {
            "scope": "security", "dry_run": False, "output": output[-12000:],
            "reboot_required": reboot_required, "rebooted": False,
        }


def register_builtin_handlers(runner, config: dict) -> Dict[str, Any]:
    registered = {
        "backup": BackupJobHandler(config),
        "restore": RestoreJobHandler(config),
        "update": UpdateJobHandler(config),
        "cleanup": CleanupJobHandler(config),
        "healthcheck": HealthCheckJobHandler(),
    }
    for job_type, handler in registered.items():
        runner.register_handler(job_type, handler)
    return registered
