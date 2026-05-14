"""
Pi Control Panel - Backup Service

Handles scheduled local exports, encrypted database backup bundles,
Google Drive upload, and 90-day backup-file retention.
"""

import asyncio
import base64
import csv
import json
import os
import shutil
import socket
import sqlite3
import tarfile
import tempfile
from datetime import date, datetime, time as dt_time, timedelta, timezone
from pathlib import Path
from typing import Any, Dict, List, Optional, Sequence

import aiofiles
import httpx
import structlog
from cryptography.hazmat.primitives.ciphers.aead import AESGCM
from cryptography.hazmat.primitives.ciphers import Cipher, algorithms, modes

from config import settings
from db import get_control_db, get_telemetry_db

logger = structlog.get_logger(__name__)

DRIVE_SCOPE = "https://www.googleapis.com/auth/drive.file"
DEVICE_CODE_ENDPOINT = "https://oauth2.googleapis.com/device/code"
TOKEN_ENDPOINT = "https://oauth2.googleapis.com/token"
BACKUP_PREFIX = "pi-control_backup_"
BACKUP_SUFFIX = ".tar.gz.enc"


class GDriveBackupService:
    """Service for local exports, encrypted backups, and Google Drive sync."""

    SETTING_LAST_DAILY_EXPORT_DATE = "backup.daily.last_export_date"
    SETTING_GDRIVE_FOLDER_ID = "backup.gdrive.folder_id"
    SETTING_GDRIVE_LAST_UPLOAD = "backup.gdrive.last_upload"

    def __init__(self):
        self.creds = None
        self.service = None
        self.folder_id: Optional[str] = None
        self.backup_dir = Path(settings.backup_local_dir)
        self.credentials_file = Path(settings.backup_gdrive_client_file)
        self.token_file = Path(settings.backup_gdrive_token_file)
        self.encryption_key_file = Path(settings.backup_encryption_key_file)
        self._running = False
        self._task: Optional[asyncio.Task] = None
        self._initialized = False
        self._folder_cache: Dict[tuple, str] = {}
        self._pending_device_auth: Optional[Dict[str, Any]] = None
        self.next_run_at: Optional[str] = None
        self.last_backup: Optional[Dict] = None
        self.backup_history: List[Dict] = []
        self.last_daily_export_date: Optional[str] = None
        self.last_gdrive_upload: Optional[Dict] = None

    def is_configured(self) -> bool:
        return self.credentials_file.exists()

    def is_authenticated(self) -> bool:
        return self.token_file.exists()

    def _gdrive_active(self) -> bool:
        return self.is_configured() and self.is_authenticated()

    async def initialize(self) -> bool:
        """Prepare directories and load runtime markers."""
        self.backup_dir = Path(os.getenv("BACKUP_LOCAL_DIR", settings.backup_local_dir))
        self.credentials_file = Path(os.getenv("BACKUP_GDRIVE_CLIENT_FILE", settings.backup_gdrive_client_file))
        self.token_file = Path(os.getenv("BACKUP_GDRIVE_TOKEN_FILE", settings.backup_gdrive_token_file))
        self.encryption_key_file = Path(os.getenv("BACKUP_ENCRYPTION_KEY_FILE", settings.backup_encryption_key_file))
        self.backup_dir.mkdir(parents=True, exist_ok=True)
        await self._ensure_settings_table()
        await self._load_runtime_settings()
        self._initialized = True
        logger.info("Backup service initialized", gdrive_configured=self.is_configured(), gdrive_authenticated=self.is_authenticated())
        return self._gdrive_active()

    async def _ensure_ready(self):
        if not self._initialized:
            await self.initialize()

    async def _ensure_settings_table(self):
        db = await get_control_db()
        await db.execute(
            """
            CREATE TABLE IF NOT EXISTS settings (
                key TEXT PRIMARY KEY,
                value TEXT NOT NULL,
                updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
            )
            """
        )
        await db.commit()

    async def _get_setting(self, key: str) -> Optional[str]:
        db = await get_control_db()
        cursor = await db.execute("SELECT value FROM settings WHERE key = ?", (key,))
        row = await cursor.fetchone()
        return row[0] if row else None

    async def _set_setting(self, key: str, value: str):
        db = await get_control_db()
        await db.execute(
            """
            INSERT INTO settings (key, value, updated_at)
            VALUES (?, ?, CURRENT_TIMESTAMP)
            ON CONFLICT(key) DO UPDATE SET
                value = excluded.value,
                updated_at = CURRENT_TIMESTAMP
            """,
            (key, value),
        )
        await db.commit()

    async def _delete_setting(self, key: str):
        db = await get_control_db()
        await db.execute("DELETE FROM settings WHERE key = ?", (key,))
        await db.commit()

    async def _load_runtime_settings(self):
        self.last_daily_export_date = await self._get_setting(self.SETTING_LAST_DAILY_EXPORT_DATE)
        self.folder_id = await self._get_setting(self.SETTING_GDRIVE_FOLDER_ID)
        last_upload = await self._get_setting(self.SETTING_GDRIVE_LAST_UPLOAD)
        self.last_gdrive_upload = json.loads(last_upload) if last_upload else None

    async def start_scheduler(self):
        enabled = os.getenv("BACKUP_DAILY_EXPORT_ENABLED", str(settings.backup_daily_export_enabled))
        if enabled.lower() in {"0", "false", "no", "off"}:
            logger.info("Backup scheduler disabled by configuration")
            return

        await self._ensure_ready()
        if self._running:
            return

        self._running = True
        self._task = asyncio.create_task(self._scheduler_loop())
        logger.info("Backup scheduler started")

    async def stop_scheduler(self):
        self._running = False
        self.next_run_at = None
        if self._task:
            self._task.cancel()
            try:
                await self._task
            except asyncio.CancelledError:
                pass
        logger.info("Backup scheduler stopped")

    async def _scheduler_loop(self):
        while self._running:
            next_run = self._compute_next_run(datetime.now())
            self.next_run_at = next_run.isoformat()
            wait_seconds = max((next_run - datetime.now()).total_seconds(), 1)

            logger.info("Next backup maintenance scheduled", next_run=self.next_run_at, wait_seconds=round(wait_seconds, 2))

            try:
                await asyncio.sleep(wait_seconds)
                await self.run_maintenance_cycle(trigger="scheduled")
            except asyncio.CancelledError:
                break
            except Exception as exc:
                logger.error("Backup scheduler error", error=str(exc))
                await asyncio.sleep(300)

    def _compute_next_run(self, now: datetime) -> datetime:
        target = now.replace(
            hour=max(0, min(settings.backup_daily_export_hour, 23)),
            minute=max(0, min(settings.backup_daily_export_minute, 59)),
            second=0,
            microsecond=0,
        )
        if now >= target:
            target += timedelta(days=1)
        return target

    async def run_maintenance_cycle(self, trigger: str = "scheduled") -> Dict:
        """Run daily export, encrypted cloud backup, and file retention."""
        await self._ensure_ready()
        started_at = datetime.now()
        result: Dict[str, Any] = {
            "type": "maintenance",
            "trigger": trigger,
            "started_at": started_at.isoformat(),
            "status": "running",
            "daily_export": None,
            "encrypted_backup": None,
            "retention": None,
            "backup_file_retention": None,
            "errors": [],
        }

        try:
            if settings.backup_daily_export_enabled:
                result["daily_export"] = await self.export_pending_daily_data()
                if result["daily_export"].get("status") == "failed":
                    result["errors"].extend(result["daily_export"].get("errors", []))

            result["encrypted_backup"] = await self.run_encrypted_backup(trigger=trigger)
            if result["encrypted_backup"].get("status") == "failed":
                result["errors"].extend(result["encrypted_backup"].get("errors", []))

            result["retention"] = await self.enforce_retention()
            if result["retention"].get("status") == "failed":
                result["errors"].extend(result["retention"].get("errors", []))

            result["backup_file_retention"] = await self.enforce_backup_file_retention()
            if result["backup_file_retention"].get("status") == "failed":
                result["errors"].extend(result["backup_file_retention"].get("errors", []))

            result["status"] = "completed" if not result["errors"] else "completed_with_errors"
        except Exception as exc:
            logger.error("Maintenance cycle failed", error=str(exc))
            result["status"] = "failed"
            result["errors"].append(str(exc))

        result["completed_at"] = datetime.now().isoformat()
        result["duration_seconds"] = round((datetime.now() - started_at).total_seconds(), 2)
        self._record_result(result)
        return result

    async def run_backup(self, format: str = "json") -> Dict:
        """Manually export the most recent 24 hours."""
        await self._ensure_ready()
        end_dt = datetime.now()
        start_dt = end_dt - timedelta(hours=24)
        stamp = end_dt.strftime("%Y%m%d-%H%M%S")
        result = await self._export_window(
            start_dt=start_dt,
            end_dt=end_dt,
            format=format,
            scope="manual",
            stamp=stamp,
            target_date=end_dt.date(),
            upload_to_cloud=False,
            require_cloud_if_configured=False,
        )
        result["type"] = "manual_backup"
        self._record_result(result)
        return result

    async def export_pending_daily_data(self, format: Optional[str] = None) -> Dict:
        """Export the most recent completed local day once."""
        await self._ensure_ready()
        target_date = datetime.now().date() - timedelta(days=1)
        target_day = target_date.isoformat()

        if self.last_daily_export_date == target_day:
            return {
                "type": "daily_export",
                "date": target_day,
                "status": "skipped",
                "reason": "already_exported",
                "files": [],
                "errors": [],
            }

        day_start = datetime.combine(target_date, dt_time.min)
        day_end = day_start + timedelta(days=1)
        result = await self._export_window(
            start_dt=day_start,
            end_dt=day_end,
            format=format or settings.backup_default_format,
            scope="daily",
            stamp=target_day,
            target_date=target_date,
            upload_to_cloud=False,
            require_cloud_if_configured=False,
        )
        result["type"] = "daily_export"
        result["date"] = target_day

        if result["status"] in {"completed", "completed_no_data", "completed_local_only"}:
            self.last_daily_export_date = target_day
            await self._set_setting(self.SETTING_LAST_DAILY_EXPORT_DATE, target_day)

        return result

    async def run_encrypted_backup(self, trigger: str = "manual") -> Dict:
        """Create an encrypted archive and upload it to Google Drive when authorized."""
        await self._ensure_ready()
        started_at = datetime.now()
        stamp = started_at.strftime("%Y-%m-%d_%H%M%S")
        filename = f"{BACKUP_PREFIX}{stamp}{BACKUP_SUFFIX}"
        output_path = self.backup_dir / filename

        result: Dict[str, Any] = {
            "type": "encrypted_backup",
            "trigger": trigger,
            "status": "running",
            "filename": filename,
            "path": str(output_path),
            "uploaded": False,
            "gdrive_file": None,
            "errors": [],
        }

        try:
            archive_path, manifest = await asyncio.to_thread(self._build_encrypted_archive, output_path, stamp)
            result["path"] = str(archive_path)
            result["size_bytes"] = archive_path.stat().st_size
            result["manifest"] = manifest

            if self._gdrive_active():
                upload = await asyncio.to_thread(self._upload_file_to_drive, archive_path)
                result["uploaded"] = True
                result["gdrive_file"] = upload
                self.last_gdrive_upload = upload
                await self._set_setting(self.SETTING_GDRIVE_LAST_UPLOAD, json.dumps(upload))
            else:
                result["status"] = "completed_local_only"
                result["reason"] = "gdrive_not_authenticated"

            if result["status"] == "running":
                result["status"] = "completed"
        except Exception as exc:
            logger.error("Encrypted backup failed", error=str(exc))
            result["status"] = "failed"
            result["errors"].append(str(exc))

        result["completed_at"] = datetime.now().isoformat()
        result["duration_seconds"] = round((datetime.now() - started_at).total_seconds(), 2)
        self._record_result(result)
        return result

    def _build_encrypted_archive(self, output_path: Path, stamp: str) -> tuple[Path, Dict[str, Any]]:
        output_path.parent.mkdir(parents=True, exist_ok=True)
        with tempfile.TemporaryDirectory(prefix="pi-control-backup-") as tmp_dir_str:
            tmp_dir = Path(tmp_dir_str)
            payload_dir = tmp_dir / "payload"
            db_dir = payload_dir / "databases"
            exports_dir = payload_dir / "exports"
            db_dir.mkdir(parents=True)
            exports_dir.mkdir(parents=True)

            included_files: List[Dict[str, Any]] = []
            for label, db_path in (
                ("control", Path(settings.database_path)),
                ("telemetry", Path(settings.telemetry_db_path)),
            ):
                snapshot_path = db_dir / f"{label}.db"
                if self._snapshot_sqlite_db(db_path, snapshot_path):
                    included_files.append({"type": "database", "name": snapshot_path.relative_to(payload_dir).as_posix(), "size_bytes": snapshot_path.stat().st_size})

            for export_path in self._iter_local_export_files():
                target = exports_dir / export_path.name
                shutil.copy2(export_path, target)
                included_files.append({"type": "export", "name": target.relative_to(payload_dir).as_posix(), "size_bytes": target.stat().st_size})

            manifest = {
                "created_at": datetime.now(timezone.utc).isoformat(),
                "stamp": stamp,
                "hostname": socket.gethostname(),
                "app": "pi-control",
                "version": "1.0.0",
                "retention_days": settings.backup_retention_days,
                "encrypted": True,
                "included_files": included_files,
            }
            manifest_path = payload_dir / "manifest.json"
            manifest_path.write_text(json.dumps(manifest, indent=2), encoding="utf-8")

            tar_path = tmp_dir / f"{stamp}.tar.gz"
            with tarfile.open(tar_path, "w:gz") as tar:
                tar.add(payload_dir, arcname="pi-control-backup")

            key = self._get_or_create_encryption_key()
            nonce = os.urandom(12)
            self._encrypt_file(tar_path, output_path, key, nonce)
            try:
                os.chmod(output_path, 0o600)
            except PermissionError:
                pass

        return output_path, manifest

    def _encrypt_file(self, source_path: Path, output_path: Path, key: bytes, nonce: bytes):
        encryptor = Cipher(algorithms.AES(key), modes.GCM(nonce)).encryptor()
        with source_path.open("rb") as src, output_path.open("wb") as dst:
            dst.write(b"PCBACKUP1")
            dst.write(nonce)
            while True:
                chunk = src.read(1024 * 1024)
                if not chunk:
                    break
                dst.write(encryptor.update(chunk))
            dst.write(encryptor.finalize())
            dst.write(encryptor.tag)

    def _snapshot_sqlite_db(self, source_path: Path, target_path: Path) -> bool:
        if str(source_path) == ":memory:" or not source_path.exists():
            return False
        target_path.parent.mkdir(parents=True, exist_ok=True)
        source = sqlite3.connect(str(source_path))
        try:
            dest = sqlite3.connect(str(target_path))
            try:
                source.backup(dest)
            finally:
                dest.close()
        finally:
            source.close()
        return True

    def _iter_local_export_files(self) -> List[Path]:
        if not self.backup_dir.exists():
            return []
        return sorted(
            path for path in self.backup_dir.iterdir()
            if path.is_file()
            and path.suffix in {".json", ".csv"}
            and path.name.startswith(("manual_", "daily_", "archive_"))
        )

    def _get_or_create_encryption_key(self) -> bytes:
        if self.encryption_key_file.exists():
            return base64.urlsafe_b64decode(self.encryption_key_file.read_text().strip().encode())
        key = AESGCM.generate_key(bit_length=256)
        self.encryption_key_file.parent.mkdir(parents=True, exist_ok=True)
        self.encryption_key_file.write_text(base64.urlsafe_b64encode(key).decode(), encoding="utf-8")
        try:
            os.chmod(self.encryption_key_file, 0o600)
        except PermissionError:
            pass
        return key

    async def enforce_retention(self, format: Optional[str] = None) -> Dict:
        """Archive expired telemetry/IoT days and remove them from local storage."""
        await self._ensure_ready()
        db = await get_telemetry_db()
        export_format = self._normalize_format(format or settings.backup_default_format)
        max_days = max(1, settings.backup_archive_max_days_per_cycle)

        result = {
            "type": "retention",
            "status": "completed",
            "format": export_format,
            "telemetry": {"archived_days": 0, "deleted_rows": 0, "files": []},
            "iot": {"archived_days": 0, "deleted_rows": 0, "files": []},
            "errors": [],
        }

        telemetry_days = await self._list_expired_days(db, "metrics_raw", "ts", settings.telemetry_raw_retention_days, max_days)
        for archive_day in telemetry_days:
            archive_result = await self._archive_and_delete_day(db, "telemetry", archive_day, export_format)
            result["telemetry"]["deleted_rows"] += archive_result["deleted_rows"]
            result["telemetry"]["files"].extend(archive_result["files"])
            if archive_result["status"] == "completed":
                result["telemetry"]["archived_days"] += 1
            else:
                result["errors"].extend(archive_result["errors"])
                break

        iot_days = await self._list_expired_days(db, "iot_sensor_readings", "timestamp", settings.iot_sensor_retention_days, max_days)
        for archive_day in iot_days:
            archive_result = await self._archive_and_delete_day(db, "iot", archive_day, export_format)
            result["iot"]["deleted_rows"] += archive_result["deleted_rows"]
            result["iot"]["files"].extend(archive_result["files"])
            if archive_result["status"] == "completed":
                result["iot"]["archived_days"] += 1
            else:
                result["errors"].extend(archive_result["errors"])
                break

        total_deleted = result["telemetry"]["deleted_rows"] + result["iot"]["deleted_rows"]
        if total_deleted > 1000:
            await db.execute("VACUUM")
            await db.commit()

        if result["errors"]:
            result["status"] = "failed"

        return result

    async def enforce_backup_file_retention(self) -> Dict:
        """Delete old local and Drive backup files created by Pi Control."""
        await self._ensure_ready()
        result: Dict[str, Any] = {
            "type": "backup_file_retention",
            "status": "completed",
            "retention_days": settings.backup_retention_days,
            "local_deleted": [],
            "remote_deleted": [],
            "errors": [],
        }
        cutoff = datetime.now() - timedelta(days=max(1, settings.backup_retention_days))

        for path in self._iter_retention_candidate_files():
            try:
                if datetime.fromtimestamp(path.stat().st_mtime) < cutoff:
                    path.unlink()
                    result["local_deleted"].append(path.name)
            except Exception as exc:
                result["errors"].append(f"local:{path.name}:{exc}")

        if self._gdrive_active():
            try:
                remote_deleted = await asyncio.to_thread(self._delete_expired_drive_backups, cutoff)
                result["remote_deleted"].extend(remote_deleted)
            except Exception as exc:
                result["errors"].append(f"drive:{exc}")

        if result["errors"]:
            result["status"] = "failed"
        return result

    def _iter_retention_candidate_files(self) -> List[Path]:
        if not self.backup_dir.exists():
            return []
        return sorted(
            path for path in self.backup_dir.iterdir()
            if path.is_file()
            and (
                (path.name.startswith(BACKUP_PREFIX) and path.name.endswith(BACKUP_SUFFIX))
                or (path.name.startswith(("manual_", "daily_", "archive_")) and path.suffix in {".json", ".csv"})
            )
        )

    async def _list_expired_days(self, db, table: str, ts_column: str, retention_days: int, limit: int) -> List[date]:
        cutoff_date = (datetime.now() - timedelta(days=retention_days)).date().isoformat()
        cursor = await db.execute(
            f"""
            SELECT DISTINCT date({ts_column}, 'unixepoch', 'localtime') AS archive_day
            FROM {table}
            WHERE date({ts_column}, 'unixepoch', 'localtime') < ?
            ORDER BY archive_day
            LIMIT ?
            """,
            (cutoff_date, limit),
        )
        rows = await cursor.fetchall()
        return [date.fromisoformat(row[0]) for row in rows if row and row[0]]

    async def _archive_and_delete_day(self, db, data_type: str, archive_day: date, format: str) -> Dict:
        day_start = datetime.combine(archive_day, dt_time.min)
        day_end = day_start + timedelta(days=1)
        export_result = await self._export_window(
            start_dt=day_start,
            end_dt=day_end,
            format=format,
            scope="archive",
            stamp=archive_day.isoformat(),
            target_date=archive_day,
            upload_to_cloud=False,
            require_cloud_if_configured=False,
            data_types=(data_type,),
        )

        if export_result["status"] not in {"completed", "completed_no_data", "completed_local_only"}:
            return {"status": "failed", "deleted_rows": 0, "files": export_result.get("files", []), "errors": export_result.get("errors", [])}

        start_ts = int(day_start.timestamp())
        end_ts = int(day_end.timestamp())
        if data_type == "telemetry":
            cursor = await db.execute("DELETE FROM metrics_raw WHERE ts >= ? AND ts < ?", (start_ts, end_ts))
        else:
            cursor = await db.execute("DELETE FROM iot_sensor_readings WHERE timestamp >= ? AND timestamp < ?", (start_ts, end_ts))
        await db.commit()

        return {"status": "completed", "deleted_rows": cursor.rowcount or 0, "files": export_result.get("files", []), "errors": []}

    async def _export_window(
        self,
        start_dt: datetime,
        end_dt: datetime,
        format: str,
        scope: str,
        stamp: str,
        target_date: date,
        upload_to_cloud: bool,
        require_cloud_if_configured: bool,
        data_types: Sequence[str] = ("telemetry", "iot"),
    ) -> Dict:
        db = await get_telemetry_db()
        export_format = self._normalize_format(format)
        start_ts = int(start_dt.timestamp())
        end_ts = int(end_dt.timestamp())

        result = {"scope": scope, "format": export_format, "start": start_dt.isoformat(), "end": end_dt.isoformat(), "status": "running", "files": [], "errors": []}

        try:
            for data_type in data_types:
                file_info = await self._export_dataset(
                    db=db,
                    data_type=data_type,
                    start_ts=start_ts,
                    end_ts=end_ts,
                    export_format=export_format,
                    scope=scope,
                    stamp=stamp,
                    target_date=target_date,
                    upload_to_cloud=upload_to_cloud,
                    require_cloud_if_configured=require_cloud_if_configured,
                )
                if file_info:
                    result["files"].append(file_info)

            if result["errors"]:
                result["status"] = "failed"
            elif not result["files"]:
                result["status"] = "completed_no_data"
            else:
                result["status"] = "completed"
        except Exception as exc:
            logger.error("Export window failed", scope=scope, error=str(exc))
            result["status"] = "failed"
            result["errors"].append(str(exc))

        result["completed_at"] = datetime.now().isoformat()
        return result

    async def _export_dataset(
        self,
        db,
        data_type: str,
        start_ts: int,
        end_ts: int,
        export_format: str,
        scope: str,
        stamp: str,
        target_date: date,
        upload_to_cloud: bool,
        require_cloud_if_configured: bool,
    ) -> Optional[Dict]:
        if data_type == "telemetry":
            cursor = await db.execute("SELECT ts, metric, labels_json, value FROM metrics_raw WHERE ts >= ? AND ts < ? ORDER BY ts", (start_ts, end_ts))
            rows = await cursor.fetchall()
        elif data_type == "iot":
            cursor = await db.execute(
                "SELECT device_id, sensor_type, value, unit, timestamp FROM iot_sensor_readings WHERE timestamp >= ? AND timestamp < ? ORDER BY timestamp",
                (start_ts, end_ts),
            )
            rows = await cursor.fetchall()
        else:
            raise ValueError(f"Unsupported data type: {data_type}")

        if not rows:
            return None

        filename = self._build_filename(scope=scope, stamp=stamp, data_type=data_type, export_format=export_format)
        filepath = self.backup_dir / filename
        await self._write_export_file(filepath=filepath, data_type=data_type, rows=rows, export_format=export_format)

        return {"type": data_type, "filename": filename, "path": str(filepath), "rows": len(rows), "uploaded": False}

    async def _write_export_file(self, filepath: Path, data_type: str, rows: List, export_format: str):
        if export_format == "json":
            data = []
            if data_type == "telemetry":
                for row in rows:
                    data.append({"timestamp": row[0], "datetime": datetime.fromtimestamp(row[0]).isoformat(), "metric": row[1], "labels": json.loads(row[2]) if row[2] else {}, "value": row[3]})
            else:
                for row in rows:
                    data.append({"device_id": row[0], "sensor_type": row[1], "value": row[2], "unit": row[3], "timestamp": row[4], "datetime": datetime.fromtimestamp(row[4]).isoformat()})
            async with aiofiles.open(filepath, "w") as handle:
                await handle.write(json.dumps(data, indent=2, ensure_ascii=False))
            return

        with open(filepath, "w", newline="", encoding="utf-8") as handle:
            writer = csv.writer(handle)
            if data_type == "telemetry":
                writer.writerow(["timestamp", "datetime", "metric", "labels", "value"])
                for row in rows:
                    writer.writerow([row[0], datetime.fromtimestamp(row[0]).isoformat(), row[1], row[2], row[3]])
            else:
                writer.writerow(["device_id", "sensor_type", "value", "unit", "timestamp", "datetime"])
                for row in rows:
                    writer.writerow([row[0], row[1], row[2], row[3], row[4], datetime.fromtimestamp(row[4]).isoformat()])

    def _build_filename(self, scope: str, stamp: str, data_type: str, export_format: str) -> str:
        return f"{scope}_{stamp}_{data_type}.{export_format}"

    def _normalize_format(self, export_format: str) -> str:
        return "csv" if str(export_format).lower() == "csv" else "json"

    def _record_result(self, result: Dict):
        self.last_backup = result
        self.backup_history.append(result)
        if len(self.backup_history) > 30:
            self.backup_history = self.backup_history[-30:]

    async def upload_oauth_client(self, content: bytes) -> Dict[str, Any]:
        await self._ensure_ready()
        config = json.loads(content.decode("utf-8"))
        client = self._extract_oauth_client(config)
        self.credentials_file.parent.mkdir(parents=True, exist_ok=True)
        self.credentials_file.write_text(json.dumps(config, indent=2), encoding="utf-8")
        try:
            os.chmod(self.credentials_file, 0o600)
        except PermissionError:
            pass
        return {"configured": True, "client_id": self._mask_client_id(client["client_id"])}

    async def start_device_authorization(self) -> Dict[str, Any]:
        await self._ensure_ready()
        client = self._load_oauth_client()
        async with httpx.AsyncClient(timeout=10.0) as http:
            response = await http.post(DEVICE_CODE_ENDPOINT, data={"client_id": client["client_id"], "scope": DRIVE_SCOPE})
        if response.status_code >= 400:
            raise RuntimeError(response.text)
        payload = response.json()
        expires_at = datetime.now(timezone.utc) + timedelta(seconds=int(payload.get("expires_in", 1800)))
        self._pending_device_auth = {
            "device_code": payload["device_code"],
            "user_code": payload["user_code"],
            "verification_url": payload["verification_url"],
            "expires_at": expires_at,
            "interval": int(payload.get("interval", 5)),
            "client_id": client["client_id"],
            "client_secret": client["client_secret"],
        }
        return self._device_auth_public_status("pending")

    async def poll_device_authorization(self) -> Dict[str, Any]:
        await self._ensure_ready()
        if not self._pending_device_auth:
            return {"status": "not_started", "authenticated": self.is_authenticated()}
        if datetime.now(timezone.utc) >= self._pending_device_auth["expires_at"]:
            self._pending_device_auth = None
            return {"status": "expired", "authenticated": False}

        pending = self._pending_device_auth
        async with httpx.AsyncClient(timeout=10.0) as http:
            response = await http.post(
                TOKEN_ENDPOINT,
                data={
                    "client_id": pending["client_id"],
                    "client_secret": pending["client_secret"],
                    "device_code": pending["device_code"],
                    "grant_type": "urn:ietf:params:oauth:grant-type:device_code",
                },
            )

        if response.status_code == 428:
            return self._device_auth_public_status("pending")
        data = response.json()
        if data.get("error") in {"authorization_pending", "slow_down"}:
            if data.get("error") == "slow_down":
                pending["interval"] += 5
            return self._device_auth_public_status(data["error"])
        if response.status_code >= 400:
            self._pending_device_auth = None
            return {"status": "failed", "authenticated": False, "error": data.get("error_description") or data.get("error") or response.text}

        token = {
            "token": data["access_token"],
            "refresh_token": data.get("refresh_token"),
            "token_uri": TOKEN_ENDPOINT,
            "client_id": pending["client_id"],
            "client_secret": pending["client_secret"],
            "scopes": [DRIVE_SCOPE],
            "expiry": (datetime.now(timezone.utc) + timedelta(seconds=int(data.get("expires_in", 3600)))).isoformat(),
        }
        self.token_file.parent.mkdir(parents=True, exist_ok=True)
        self.token_file.write_text(json.dumps(token, indent=2), encoding="utf-8")
        try:
            os.chmod(self.token_file, 0o600)
        except PermissionError:
            pass
        self._pending_device_auth = None
        return {"status": "authenticated", "authenticated": True}

    def _device_auth_public_status(self, status: str) -> Dict[str, Any]:
        pending = self._pending_device_auth or {}
        return {
            "status": status,
            "authenticated": False,
            "user_code": pending.get("user_code"),
            "verification_url": pending.get("verification_url"),
            "expires_at": pending.get("expires_at").isoformat() if pending.get("expires_at") else None,
            "interval": pending.get("interval", 5),
        }

    async def disconnect_gdrive(self) -> Dict[str, Any]:
        await self._ensure_ready()
        if self.token_file.exists():
            self.token_file.unlink()
        self._pending_device_auth = None
        self.service = None
        self.creds = None
        self.last_gdrive_upload = None
        await self._delete_setting(self.SETTING_GDRIVE_LAST_UPLOAD)
        return {"disconnected": True}

    def _load_oauth_client(self) -> Dict[str, str]:
        if not self.credentials_file.exists():
            raise RuntimeError("Google Drive OAuth client is not configured")
        return self._extract_oauth_client(json.loads(self.credentials_file.read_text()))

    def _extract_oauth_client(self, config: Dict[str, Any]) -> Dict[str, str]:
        candidates = []
        for key in ("installed", "web", "tv", "device"):
            value = config.get(key)
            if isinstance(value, dict):
                candidates.append(value)
        candidates.append(config)
        for candidate in candidates:
            client_id = candidate.get("client_id")
            client_secret = candidate.get("client_secret")
            if client_id and client_secret:
                return {"client_id": client_id, "client_secret": client_secret}
        raise ValueError("OAuth client JSON must include client_id and client_secret")

    def _mask_client_id(self, client_id: str) -> str:
        if len(client_id) <= 12:
            return "***"
        return f"{client_id[:6]}...{client_id[-6:]}"

    def _get_drive_service(self):
        from google.auth.transport.requests import Request
        from google.oauth2.credentials import Credentials
        from googleapiclient.discovery import build

        if not self.token_file.exists():
            raise RuntimeError("Google Drive is not authenticated")
        token = json.loads(self.token_file.read_text())
        creds = Credentials(
            token=token.get("token"),
            refresh_token=token.get("refresh_token"),
            token_uri=token.get("token_uri", TOKEN_ENDPOINT),
            client_id=token.get("client_id"),
            client_secret=token.get("client_secret"),
            scopes=token.get("scopes") or [DRIVE_SCOPE],
        )
        expiry = token.get("expiry")
        if expiry:
            try:
                creds.expiry = datetime.fromisoformat(expiry.replace("Z", "+00:00")).replace(tzinfo=None)
            except ValueError:
                pass
        if creds.expired and creds.refresh_token:
            creds.refresh(Request())
            token["token"] = creds.token
            token["expiry"] = creds.expiry.isoformat() if creds.expiry else None
            self.token_file.write_text(json.dumps(token, indent=2), encoding="utf-8")
        return build("drive", "v3", credentials=creds, cache_discovery=False)

    def _ensure_drive_folder(self, service=None) -> str:
        service = service or self._get_drive_service()
        if self.folder_id:
            return self.folder_id
        folder_name = settings.backup_gdrive_folder_name
        query = (
            "mimeType='application/vnd.google-apps.folder' "
            f"and name='{folder_name.replace(chr(39), chr(92) + chr(39))}' and trashed=false"
        )
        found = service.files().list(q=query, spaces="drive", fields="files(id,name)", pageSize=10).execute().get("files", [])
        if found:
            self.folder_id = found[0]["id"]
            return self.folder_id
        metadata = {"name": folder_name, "mimeType": "application/vnd.google-apps.folder"}
        folder = service.files().create(body=metadata, fields="id,name").execute()
        self.folder_id = folder["id"]
        return self.folder_id

    def _upload_file_to_drive(self, filepath: Path) -> Dict[str, Any]:
        from googleapiclient.http import MediaFileUpload

        service = self._get_drive_service()
        folder_id = self._ensure_drive_folder(service)
        metadata = {"name": filepath.name, "parents": [folder_id]}
        media = MediaFileUpload(str(filepath), mimetype="application/octet-stream", resumable=False)
        created = service.files().create(body=metadata, media_body=media, fields="id,name,createdTime,size,webViewLink").execute()
        return {
            "id": created.get("id"),
            "name": created.get("name"),
            "createdTime": created.get("createdTime"),
            "size": int(created.get("size", 0) or 0),
            "webViewLink": created.get("webViewLink"),
        }

    def list_drive_backups(self) -> List[Dict[str, Any]]:
        if not self._gdrive_active():
            return []
        service = self._get_drive_service()
        folder_id = self._ensure_drive_folder(service)
        query = f"'{folder_id}' in parents and trashed=false"
        items = service.files().list(
            q=query,
            spaces="drive",
            fields="files(id,name,createdTime,modifiedTime,size,webViewLink)",
            orderBy="createdTime desc",
            pageSize=100,
        ).execute().get("files", [])
        return [
            {
                "id": item.get("id"),
                "name": item.get("name"),
                "createdTime": item.get("createdTime"),
                "modifiedTime": item.get("modifiedTime"),
                "size": int(item.get("size", 0) or 0),
                "webViewLink": item.get("webViewLink"),
            }
            for item in items
            if item.get("name", "").startswith(BACKUP_PREFIX) and item.get("name", "").endswith(BACKUP_SUFFIX)
        ]

    def delete_drive_backup(self, file_id: str) -> Dict[str, Any]:
        if not self._gdrive_active():
            raise RuntimeError("Google Drive is not authenticated")
        service = self._get_drive_service()
        file_meta = service.files().get(fileId=file_id, fields="id,name,parents").execute()
        folder_id = self._ensure_drive_folder(service)
        if folder_id not in file_meta.get("parents", []) or not file_meta.get("name", "").startswith(BACKUP_PREFIX):
            raise RuntimeError("Refusing to delete a non Pi Control backup file")
        service.files().delete(fileId=file_id).execute()
        return {"deleted": True, "id": file_id, "name": file_meta.get("name")}

    def _delete_expired_drive_backups(self, cutoff: datetime) -> List[str]:
        deleted: List[str] = []
        for item in self.list_drive_backups():
            created = self._parse_drive_time(item.get("createdTime"))
            if created and created.replace(tzinfo=None) < cutoff:
                self.delete_drive_backup(item["id"])
                deleted.append(item["name"])
        return deleted

    def _parse_drive_time(self, value: Optional[str]) -> Optional[datetime]:
        if not value:
            return None
        try:
            return datetime.fromisoformat(value.replace("Z", "+00:00"))
        except ValueError:
            return None

    def set_folder_id(self, folder_ref: str) -> str:
        self.folder_id = folder_ref
        return folder_ref

    def get_status(self) -> Dict:
        """Get current scheduler and backup status."""
        gdrive_configured = self.is_configured()
        gdrive_authenticated = self.is_authenticated()
        remote_backups: List[Dict[str, Any]] = []
        remote_error = None
        if gdrive_configured and gdrive_authenticated:
            try:
                remote_backups = self.list_drive_backups()
            except Exception as exc:
                remote_error = str(exc)
        return {
            "gdrive_available": True,
            "gdrive_enabled": gdrive_configured and gdrive_authenticated,
            "configured": gdrive_configured,
            "authenticated": gdrive_authenticated,
            "scheduler_running": self._running,
            "next_run_at": self.next_run_at,
            "last_backup": self.last_backup,
            "last_daily_export_date": self.last_daily_export_date,
            "last_gdrive_upload": self.last_gdrive_upload,
            "backup_directory": str(self.backup_dir),
            "folder_id": self.folder_id,
            "folder_name": settings.backup_gdrive_folder_name,
            "retention_days": {
                "backup_files": settings.backup_retention_days,
                "telemetry": settings.telemetry_raw_retention_days,
                "iot": settings.iot_sensor_retention_days,
                "summary": settings.telemetry_summary_retention_days,
            },
            "daily_export": {
                "enabled": settings.backup_daily_export_enabled,
                "hour": settings.backup_daily_export_hour,
                "minute": settings.backup_daily_export_minute,
                "format": settings.backup_default_format,
            },
            "encryption": {
                "enabled": True,
                "key_file": str(self.encryption_key_file),
                "key_exists": self.encryption_key_file.exists(),
            },
            "auth_flow": self._device_auth_public_status("pending") if self._pending_device_auth else None,
            "local_backups": self._get_local_backups(),
            "remote_backups": remote_backups,
            "remote_error": remote_error,
        }

    def _get_local_backups(self) -> List[Dict]:
        backups = []
        if self.backup_dir.exists():
            files = sorted([path for path in self.backup_dir.iterdir() if path.is_file()], key=lambda path: path.stat().st_mtime, reverse=True)
            for path in files[:100]:
                backups.append({"filename": path.name, "size_bytes": path.stat().st_size, "modified": datetime.fromtimestamp(path.stat().st_mtime).isoformat()})
        return backups


backup_service = GDriveBackupService()
