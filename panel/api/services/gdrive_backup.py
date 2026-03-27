"""
Pi Control Panel - Backup Service

Handles scheduled daily exports and retention archiving.
Google Drive integration is temporarily disabled.
"""

import asyncio
import csv
import json
from datetime import date, datetime, time as dt_time, timedelta
from pathlib import Path
from typing import Dict, List, Optional, Sequence

import aiofiles
import structlog

from config import settings
from db import get_control_db, get_telemetry_db

logger = structlog.get_logger(__name__)
GDRIVE_DISABLED_REASON = "Temporarily disabled. TODO: redesign cloud backup flow."


class GDriveBackupService:
    """Service for local exports and retention archiving."""

    SETTING_LAST_DAILY_EXPORT_DATE = "backup.daily.last_export_date"

    def __init__(self):
        self.creds = None
        self.service = None
        self.folder_id: Optional[str] = None
        self.backup_dir = Path(settings.backup_local_dir)
        # Kept for backward compatibility with older tests/tools.
        self.credentials_file = self.backup_dir / ".gdrive_disabled_credentials"
        self.token_file = self.backup_dir / ".gdrive_disabled_token"
        self._running = False
        self._task: Optional[asyncio.Task] = None
        self._initialized = False
        self._folder_cache: Dict[tuple, str] = {}
        self.next_run_at: Optional[str] = None
        self.last_backup: Optional[Dict] = None
        self.backup_history: List[Dict] = []
        self.last_daily_export_date: Optional[str] = None

    def is_configured(self) -> bool:
        """Cloud backup is temporarily disabled."""
        return False

    def is_authenticated(self) -> bool:
        """Cloud backup is temporarily disabled."""
        return False

    async def initialize(self) -> bool:
        """Prepare directories and load runtime markers."""
        self.backup_dir.mkdir(parents=True, exist_ok=True)
        await self._ensure_settings_table()
        await self._load_runtime_settings()
        self._initialized = True
        logger.info("Cloud backup is disabled", reason=GDRIVE_DISABLED_REASON)
        return False

    async def _ensure_ready(self):
        """Lazily initialize the service when called directly."""
        if not self._initialized:
            await self.initialize()

    async def _ensure_settings_table(self):
        """Ensure the key-value settings table exists."""
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
        """Read a persisted setting."""
        db = await get_control_db()
        cursor = await db.execute("SELECT value FROM settings WHERE key = ?", (key,))
        row = await cursor.fetchone()
        return row[0] if row else None

    async def _set_setting(self, key: str, value: str):
        """Persist a setting value."""
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

    async def _load_runtime_settings(self):
        """Load scheduler markers from the database."""
        self.last_daily_export_date = await self._get_setting(self.SETTING_LAST_DAILY_EXPORT_DATE)

    async def start_scheduler(self):
        """Start scheduled daily export and retention maintenance."""
        await self._ensure_ready()
        if self._running:
            return

        self._running = True
        asyncio.create_task(self.run_maintenance_cycle(trigger="startup"))
        self._task = asyncio.create_task(self._scheduler_loop())
        logger.info("Backup scheduler started")

    async def stop_scheduler(self):
        """Stop the background scheduler."""
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
        """Run the maintenance cycle at the configured local time each day."""
        while self._running:
            next_run = self._compute_next_run(datetime.now())
            self.next_run_at = next_run.isoformat()
            wait_seconds = max((next_run - datetime.now()).total_seconds(), 1)

            logger.info(
                "Next backup maintenance scheduled",
                next_run=self.next_run_at,
                wait_seconds=round(wait_seconds, 2),
            )

            try:
                await asyncio.sleep(wait_seconds)
                await self.run_maintenance_cycle(trigger="scheduled")
            except asyncio.CancelledError:
                break
            except Exception as exc:
                logger.error("Backup scheduler error", error=str(exc))
                await asyncio.sleep(300)

    def _compute_next_run(self, now: datetime) -> datetime:
        """Compute the next scheduled local run time."""
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
        """Run daily export plus retention archival in one operation."""
        await self._ensure_ready()
        started_at = datetime.now()
        result = {
            "type": "maintenance",
            "trigger": trigger,
            "started_at": started_at.isoformat(),
            "status": "running",
            "daily_export": None,
            "retention": None,
            "errors": [],
        }

        try:
            if settings.backup_daily_export_enabled:
                result["daily_export"] = await self.export_pending_daily_data()
                if result["daily_export"].get("status") == "failed":
                    result["errors"].extend(result["daily_export"].get("errors", []))

            result["retention"] = await self.enforce_retention()
            if result["retention"].get("status") == "failed":
                result["errors"].extend(result["retention"].get("errors", []))

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

        telemetry_days = await self._list_expired_days(
            db=db,
            table="metrics_raw",
            ts_column="ts",
            retention_days=settings.telemetry_raw_retention_days,
            limit=max_days,
        )
        for archive_day in telemetry_days:
            archive_result = await self._archive_and_delete_day(db, "telemetry", archive_day, export_format)
            result["telemetry"]["deleted_rows"] += archive_result["deleted_rows"]
            result["telemetry"]["files"].extend(archive_result["files"])
            if archive_result["status"] == "completed":
                result["telemetry"]["archived_days"] += 1
            else:
                result["errors"].extend(archive_result["errors"])
                break

        iot_days = await self._list_expired_days(
            db=db,
            table="iot_sensor_readings",
            ts_column="timestamp",
            retention_days=settings.iot_sensor_retention_days,
            limit=max_days,
        )
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

    async def _list_expired_days(
        self,
        db,
        table: str,
        ts_column: str,
        retention_days: int,
        limit: int,
    ) -> List[date]:
        """List fully expired local days for a table."""
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
        """Export one expired day and delete the matching local rows on success."""
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
            return {
                "status": "failed",
                "deleted_rows": 0,
                "files": export_result.get("files", []),
                "errors": export_result.get("errors", []),
            }

        start_ts = int(day_start.timestamp())
        end_ts = int(day_end.timestamp())
        if data_type == "telemetry":
            cursor = await db.execute("DELETE FROM metrics_raw WHERE ts >= ? AND ts < ?", (start_ts, end_ts))
        else:
            cursor = await db.execute(
                "DELETE FROM iot_sensor_readings WHERE timestamp >= ? AND timestamp < ?",
                (start_ts, end_ts),
            )
        await db.commit()

        return {
            "status": "completed",
            "deleted_rows": cursor.rowcount or 0,
            "files": export_result.get("files", []),
            "errors": [],
        }

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
        """Export one time window for one or more data types."""
        db = await get_telemetry_db()
        export_format = self._normalize_format(format)
        start_ts = int(start_dt.timestamp())
        end_ts = int(end_dt.timestamp())

        result = {
            "scope": scope,
            "format": export_format,
            "start": start_dt.isoformat(),
            "end": end_dt.isoformat(),
            "status": "running",
            "files": [],
            "errors": [],
        }

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
        """Export one dataset to local backup storage."""
        if data_type == "telemetry":
            cursor = await db.execute(
                """
                SELECT ts, metric, labels_json, value
                FROM metrics_raw
                WHERE ts >= ? AND ts < ?
                ORDER BY ts
                """,
                (start_ts, end_ts),
            )
            rows = await cursor.fetchall()
        elif data_type == "iot":
            cursor = await db.execute(
                """
                SELECT device_id, sensor_type, value, unit, timestamp
                FROM iot_sensor_readings
                WHERE timestamp >= ? AND timestamp < ?
                ORDER BY timestamp
                """,
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

        file_info = {
            "type": data_type,
            "filename": filename,
            "path": str(filepath),
            "rows": len(rows),
            "uploaded": False,
        }

        if upload_to_cloud and require_cloud_if_configured:
            logger.warning("Cloud upload requested but disabled", reason=GDRIVE_DISABLED_REASON)

        return file_info

    async def _write_export_file(self, filepath: Path, data_type: str, rows: List, export_format: str):
        """Write JSON or CSV export file for telemetry or IoT rows."""
        if export_format == "json":
            data = []
            if data_type == "telemetry":
                for row in rows:
                    data.append(
                        {
                            "timestamp": row[0],
                            "datetime": datetime.fromtimestamp(row[0]).isoformat(),
                            "metric": row[1],
                            "labels": json.loads(row[2]) if row[2] else {},
                            "value": row[3],
                        }
                    )
            else:
                for row in rows:
                    data.append(
                        {
                            "device_id": row[0],
                            "sensor_type": row[1],
                            "value": row[2],
                            "unit": row[3],
                            "timestamp": row[4],
                            "datetime": datetime.fromtimestamp(row[4]).isoformat(),
                        }
                    )
            async with aiofiles.open(filepath, "w") as handle:
                await handle.write(json.dumps(data, indent=2, ensure_ascii=False))
            return

        with open(filepath, "w", newline="", encoding="utf-8") as handle:
            writer = csv.writer(handle)
            if data_type == "telemetry":
                writer.writerow(["timestamp", "datetime", "metric", "labels", "value"])
                for row in rows:
                    writer.writerow(
                        [
                            row[0],
                            datetime.fromtimestamp(row[0]).isoformat(),
                            row[1],
                            row[2],
                            row[3],
                        ]
                    )
            else:
                writer.writerow(["device_id", "sensor_type", "value", "unit", "timestamp", "datetime"])
                for row in rows:
                    writer.writerow(
                        [
                            row[0],
                            row[1],
                            row[2],
                            row[3],
                            row[4],
                            datetime.fromtimestamp(row[4]).isoformat(),
                        ]
                    )

    def _build_filename(self, scope: str, stamp: str, data_type: str, export_format: str) -> str:
        """Create stable filenames for local exports."""
        return f"{scope}_{stamp}_{data_type}.{export_format}"

    def _normalize_format(self, export_format: str) -> str:
        """Allow only JSON or CSV for export."""
        return "csv" if str(export_format).lower() == "csv" else "json"

    def _record_result(self, result: Dict):
        """Keep a short in-memory history for UI status cards."""
        self.last_backup = result
        self.backup_history.append(result)
        if len(self.backup_history) > 30:
            self.backup_history = self.backup_history[-30:]

    async def set_folder_id(self, folder_ref: str) -> str:
        """Cloud folder configuration is disabled for now."""
        raise RuntimeError(GDRIVE_DISABLED_REASON)

    def get_status(self) -> Dict:
        """Get current scheduler and local backup status."""
        return {
            "gdrive_available": False,
            "gdrive_enabled": False,
            "gdrive_todo": GDRIVE_DISABLED_REASON,
            "configured": self.is_configured(),
            "authenticated": self.is_authenticated(),
            "scheduler_running": self._running,
            "next_run_at": self.next_run_at,
            "last_backup": self.last_backup,
            "last_daily_export_date": self.last_daily_export_date,
            "backup_directory": str(self.backup_dir),
            "folder_id": None,
            "retention_days": {
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
            "local_backups": self._get_local_backups(),
        }

    def _get_local_backups(self) -> List[Dict]:
        """Return recent local export files."""
        backups = []
        if self.backup_dir.exists():
            files = sorted(
                [path for path in self.backup_dir.iterdir() if path.is_file()],
                key=lambda path: path.stat().st_mtime,
                reverse=True,
            )
            for path in files[:50]:
                backups.append(
                    {
                        "filename": path.name,
                        "size_bytes": path.stat().st_size,
                        "modified": datetime.fromtimestamp(path.stat().st_mtime).isoformat(),
                    }
                )
        return backups


# Global instance
backup_service = GDriveBackupService()
