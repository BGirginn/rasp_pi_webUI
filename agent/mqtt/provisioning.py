"""Mosquitto TLS and per-device credential provisioning."""

import ipaddress
import json
import os
import re
import secrets
import shutil
import socket
import subprocess
from datetime import datetime, timedelta, timezone
from pathlib import Path
from typing import Any, Dict

import psutil
from cryptography import x509
from cryptography.hazmat.primitives import hashes, serialization
from cryptography.hazmat.primitives.asymmetric import rsa
from cryptography.x509.oid import NameOID


DEVICE_ID_RE = re.compile(r"^[a-zA-Z0-9][a-zA-Z0-9_-]{0,63}$")


class MQTTProvisioner:
    def __init__(self, config: dict):
        mqtt = config.get("mqtt", {})
        self.host = mqtt.get("advertised_host", f"{socket.gethostname()}.local")
        self.port = int(mqtt.get("port", 8883))
        self.base_dir = Path(mqtt.get("provisioning_dir", "/etc/mosquitto/pi-control"))
        self.secrets_dir = Path(mqtt.get("secrets_dir", "/etc/pi-control/secrets"))
        self.conf_file = Path(mqtt.get("mosquitto_conf", "/etc/mosquitto/conf.d/pi-control.conf"))
        self.password_file = Path(mqtt.get("mosquitto_password_file", "/etc/mosquitto/pi-control.passwd"))
        self.acl_file = Path(mqtt.get("mosquitto_acl_file", "/etc/mosquitto/pi-control.acl"))
        self.registry_file = self.base_dir / "devices.json"
        self.ca_key = self.base_dir / "ca.key"
        self.ca_cert = self.base_dir / "ca.crt"
        self.server_key = self.base_dir / "server.key"
        self.server_cert = self.base_dir / "server.crt"
        self.panel_password_file = self.secrets_dir / "mqtt_panel_password"

    def ensure_broker(self) -> Dict[str, Any]:
        if not shutil.which("mosquitto") or not shutil.which("mosquitto_passwd"):
            raise RuntimeError("Mosquitto and mosquitto_passwd are required")
        self.base_dir.mkdir(parents=True, exist_ok=True)
        self.secrets_dir.mkdir(parents=True, exist_ok=True)
        self.conf_file.parent.mkdir(parents=True, exist_ok=True)
        self._ensure_certificates()
        if not self.panel_password_file.exists():
            self.panel_password_file.write_text(secrets.token_urlsafe(32), encoding="ascii")
            self.panel_password_file.chmod(0o600)
        panel_password = self.panel_password_file.read_text(encoding="ascii").strip()
        self._set_password("panel", panel_password)
        self._write_acl(self._load_registry())
        self._write_config()
        self._set_permissions()
        subprocess.run(["systemctl", "enable", "mosquitto"], check=True, timeout=30)
        subprocess.run(["systemctl", "restart", "mosquitto"], check=True, timeout=60)
        return self.status()

    def provision(self, device_id: str, name: str = "") -> Dict[str, Any]:
        device_id = self._validate_id(device_id)
        registry = self._load_registry()
        if device_id in registry:
            raise ValueError("Device is already provisioned; rotate its credential instead")
        self.ensure_broker()
        username = f"device_{device_id}"
        password = secrets.token_urlsafe(32)
        self._set_password(username, password)
        registry[device_id] = {
            "username": username,
            "name": (name or device_id)[:80],
            "created_at": datetime.now(timezone.utc).isoformat(),
        }
        self._save_registry(registry)
        self._write_acl(registry)
        self._reload()
        return self._credential_response(device_id, username, password)

    def rotate(self, device_id: str) -> Dict[str, Any]:
        device_id = self._validate_id(device_id)
        registry = self._load_registry()
        if device_id not in registry:
            raise KeyError("Device is not provisioned")
        password = secrets.token_urlsafe(32)
        username = registry[device_id]["username"]
        self._set_password(username, password)
        registry[device_id]["rotated_at"] = datetime.now(timezone.utc).isoformat()
        self._save_registry(registry)
        self._reload()
        return self._credential_response(device_id, username, password)

    def revoke(self, device_id: str) -> Dict[str, Any]:
        device_id = self._validate_id(device_id)
        registry = self._load_registry()
        entry = registry.pop(device_id, None)
        if not entry:
            raise KeyError("Device is not provisioned")
        subprocess.run(
            ["mosquitto_passwd", "-D", str(self.password_file), entry["username"]],
            check=True, stdout=subprocess.DEVNULL, stderr=subprocess.PIPE, timeout=15,
        )
        self._save_registry(registry)
        self._write_acl(registry)
        self._reload()
        return {"revoked": True, "device_id": device_id}

    def status(self) -> Dict[str, Any]:
        registry = self._load_registry()
        active = subprocess.run(
            ["systemctl", "is-active", "mosquitto"], capture_output=True, text=True, timeout=10
        ).stdout.strip() == "active"
        return {
            "configured": self.conf_file.exists() and self.ca_cert.exists(),
            "active": active,
            "host": self.host,
            "port": self.port,
            "tls": True,
            "anonymous": False,
            "devices": [
                {"id": device_id, **entry}
                for device_id, entry in sorted(registry.items())
            ],
        }

    def _credential_response(self, device_id: str, username: str, password: str) -> Dict[str, Any]:
        return {
            "device_id": device_id,
            "host": self.host,
            "port": self.port,
            "tls": True,
            "username": username,
            "password": password,
            "ca_certificate": self.ca_cert.read_text(encoding="ascii"),
            "topics": {
                "telemetry": f"pi-control/v1/devices/{device_id}/telemetry",
                "status": f"pi-control/v1/devices/{device_id}/status",
                "command": f"pi-control/v1/devices/{device_id}/command",
                "command_result": f"pi-control/v1/devices/{device_id}/command-result",
            },
        }

    def _ensure_certificates(self) -> None:
        if all(path.exists() for path in (self.ca_key, self.ca_cert, self.server_key, self.server_cert)):
            return
        now = datetime.now(timezone.utc)
        ca_private = rsa.generate_private_key(public_exponent=65537, key_size=3072)
        ca_name = x509.Name([x509.NameAttribute(NameOID.COMMON_NAME, "Pi Control MQTT CA")])
        ca_certificate = (
            x509.CertificateBuilder()
            .subject_name(ca_name).issuer_name(ca_name).public_key(ca_private.public_key())
            .serial_number(x509.random_serial_number()).not_valid_before(now - timedelta(minutes=5))
            .not_valid_after(now + timedelta(days=3650))
            .add_extension(x509.BasicConstraints(ca=True, path_length=0), critical=True)
            .add_extension(x509.KeyUsage(True, False, False, False, False, True, True, False, False), critical=True)
            .sign(ca_private, hashes.SHA256())
        )
        server_private = rsa.generate_private_key(public_exponent=65537, key_size=2048)
        hostname = socket.gethostname()
        names = {self.host, hostname, f"{hostname}.local", "localhost"}
        sans: list[x509.GeneralName] = [x509.DNSName(name) for name in sorted(names)]
        for values in psutil.net_if_addrs().values():
            for address in values:
                try:
                    ip = ipaddress.ip_address(address.address.split("%", 1)[0])
                except ValueError:
                    continue
                if not ip.is_loopback:
                    sans.append(x509.IPAddress(ip))
        server_name = x509.Name([x509.NameAttribute(NameOID.COMMON_NAME, self.host)])
        server_certificate = (
            x509.CertificateBuilder()
            .subject_name(server_name).issuer_name(ca_name).public_key(server_private.public_key())
            .serial_number(x509.random_serial_number()).not_valid_before(now - timedelta(minutes=5))
            .not_valid_after(now + timedelta(days=825))
            .add_extension(x509.SubjectAlternativeName(sans), critical=False)
            .add_extension(x509.ExtendedKeyUsage([x509.oid.ExtendedKeyUsageOID.SERVER_AUTH]), critical=False)
            .sign(ca_private, hashes.SHA256())
        )
        self.ca_key.write_bytes(ca_private.private_bytes(
            serialization.Encoding.PEM, serialization.PrivateFormat.PKCS8, serialization.NoEncryption()
        ))
        self.ca_cert.write_bytes(ca_certificate.public_bytes(serialization.Encoding.PEM))
        self.server_key.write_bytes(server_private.private_bytes(
            serialization.Encoding.PEM, serialization.PrivateFormat.PKCS8, serialization.NoEncryption()
        ))
        self.server_cert.write_bytes(server_certificate.public_bytes(serialization.Encoding.PEM))

    def _write_config(self) -> None:
        content = f"""# Managed by Pi Control. Manual changes are overwritten.
per_listener_settings true
listener {self.port} 0.0.0.0
allow_anonymous false
password_file {self.password_file}
acl_file {self.acl_file}
cafile {self.ca_cert}
certfile {self.server_cert}
keyfile {self.server_key}
tls_version tlsv1.2
max_packet_size 262144
"""
        self._atomic_write(self.conf_file, content, 0o644)

    def _write_acl(self, registry: Dict[str, Dict[str, Any]]) -> None:
        lines = [
            "user panel",
            "topic read pi-control/v1/devices/+/telemetry",
            "topic read pi-control/v1/devices/+/status",
            "topic read pi-control/v1/devices/+/command-result",
            "topic write pi-control/v1/devices/+/command",
        ]
        for device_id, entry in sorted(registry.items()):
            base = f"pi-control/v1/devices/{device_id}"
            lines.extend([
                "", f"user {entry['username']}",
                f"topic write {base}/telemetry", f"topic write {base}/status",
                f"topic write {base}/command-result", f"topic read {base}/command",
            ])
        self._atomic_write(self.acl_file, "\n".join(lines) + "\n", 0o640)

    def _set_password(self, username: str, password: str) -> None:
        self.password_file.parent.mkdir(parents=True, exist_ok=True)
        args = ["mosquitto_passwd", "-b"]
        if not self.password_file.exists():
            args.append("-c")
        args.extend([str(self.password_file), username, password])
        subprocess.run(
            args,
            check=True, stdout=subprocess.DEVNULL, stderr=subprocess.PIPE, timeout=15,
        )

    def _reload(self) -> None:
        subprocess.run(["systemctl", "reload-or-restart", "mosquitto"], check=True, timeout=60)

    def _load_registry(self) -> Dict[str, Dict[str, Any]]:
        if not self.registry_file.exists():
            return {}
        data = json.loads(self.registry_file.read_text(encoding="utf-8"))
        return data if isinstance(data, dict) else {}

    def _save_registry(self, registry: Dict[str, Dict[str, Any]]) -> None:
        self._atomic_write(self.registry_file, json.dumps(registry, indent=2), 0o600)

    @staticmethod
    def _atomic_write(path: Path, content: str, mode: int) -> None:
        path.parent.mkdir(parents=True, exist_ok=True)
        temporary = path.with_suffix(path.suffix + ".tmp")
        temporary.write_text(content, encoding="utf-8")
        temporary.chmod(mode)
        os.replace(temporary, path)

    def _set_permissions(self) -> None:
        for path in (self.ca_key, self.server_key):
            path.chmod(0o640)
        self.ca_cert.chmod(0o644)
        self.server_cert.chmod(0o644)
        self.password_file.chmod(0o640)
        self.acl_file.chmod(0o640)
        try:
            shutil.chown(self.base_dir, group="mosquitto")
            for path in (self.ca_key, self.server_key, self.password_file, self.acl_file):
                shutil.chown(path, group="mosquitto")
        except LookupError:
            pass

    @staticmethod
    def _validate_id(device_id: str) -> str:
        device_id = device_id.strip()
        if not DEVICE_ID_RE.fullmatch(device_id):
            raise ValueError("Device ID must contain only letters, numbers, underscore, and hyphen")
        return device_id
