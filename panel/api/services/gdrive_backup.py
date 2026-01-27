"""
Pi Control Panel - Google Drive Backup Service

Handles automatic daily backups to Google Drive.
Supports JSON, CSV, and SQLite DB export formats.
"""

import os
import json
import csv
import io
import shutil
import asyncio
from datetime import datetime, timedelta
from pathlib import Path
from typing import Optional, List, Dict
import structlog
import aiofiles

logger = structlog.get_logger()

# Google Drive API (optional - graceful fallback if not installed)
try:
    from google.oauth2.credentials import Credentials
    from google.auth.transport.requests import Request
    from google_auth_oauthlib.flow import InstalledAppFlow
    from googleapiclient.discovery import build
    from googleapiclient.http import MediaFileUpload
    GDRIVE_AVAILABLE = True
except ImportError:
    GDRIVE_AVAILABLE = False
    logger.warning("Google Drive API not installed. Run: pip install google-auth-oauthlib google-api-python-client")


SCOPES = ['https://www.googleapis.com/auth/drive.file']


class GDriveBackupService:
    """Service for backing up data to Google Drive."""
    
    def __init__(self):
        self.creds: Optional[Credentials] = None
        self.service = None
        self.folder_id: Optional[str] = None
        self.backup_dir = Path("/opt/pi-control/backups")
        self.credentials_file = Path("/opt/pi-control/credentials/gdrive_credentials.json")
        self.token_file = Path("/opt/pi-control/credentials/gdrive_token.json")
        self._running = False
        self._task = None
        self.last_backup: Optional[Dict] = None
        self.backup_history: List[Dict] = []
        
    def is_configured(self) -> bool:
        """Check if Google Drive is properly configured."""
        return GDRIVE_AVAILABLE and self.credentials_file.exists()
    
    def is_authenticated(self) -> bool:
        """Check if we have valid credentials."""
        return self.creds is not None and self.creds.valid
    
    async def initialize(self):
        """Initialize the backup service."""
        # Create backup directory
        self.backup_dir.mkdir(parents=True, exist_ok=True)
        
        if not GDRIVE_AVAILABLE:
            logger.warning("Google Drive API not available")
            return False
        
        if not self.credentials_file.exists():
            logger.info("Google Drive credentials not found. Backup to local only.")
            return False
        
        try:
            await self._authenticate()
            return True
        except Exception as e:
            logger.error(f"Failed to authenticate with Google Drive: {e}")
            return False
    
    async def _authenticate(self):
        """Authenticate with Google Drive."""
        if not GDRIVE_AVAILABLE:
            return
        
        creds = None
        
        # Load existing token
        if self.token_file.exists():
            creds = Credentials.from_authorized_user_file(str(self.token_file), SCOPES)
        
        # Refresh or get new token
        if not creds or not creds.valid:
            if creds and creds.expired and creds.refresh_token:
                creds.refresh(Request())
            else:
                # For headless Raspberry Pi, we need to use a different flow
                # The user will need to run the auth script manually once
                logger.warning("Google Drive authentication required. Run the auth script.")
                return
        
        self.creds = creds
        self.service = build('drive', 'v3', credentials=creds)
        
        # Save token for future use
        async with aiofiles.open(self.token_file, 'w') as f:
            await f.write(creds.to_json())
        
        logger.info("Google Drive authentication successful")
    
    async def start_scheduler(self):
        """Start the daily backup scheduler."""
        if self._running:
            return
        
        self._running = True
        self._task = asyncio.create_task(self._scheduler_loop())
        logger.info("Backup scheduler started")
    
    async def stop_scheduler(self):
        """Stop the backup scheduler."""
        self._running = False
        if self._task:
            self._task.cancel()
            try:
                await self._task
            except asyncio.CancelledError:
                pass
        logger.info("Backup scheduler stopped")
    
    async def _scheduler_loop(self):
        """Main scheduler loop - runs backup at midnight."""
        while self._running:
            now = datetime.now()
            
            # Calculate next midnight
            next_run = now.replace(hour=0, minute=0, second=0, microsecond=0)
            if now >= next_run:
                next_run += timedelta(days=1)
            
            wait_seconds = (next_run - now).total_seconds()
            logger.info(f"Next backup scheduled in {wait_seconds/3600:.1f} hours")
            
            try:
                await asyncio.sleep(wait_seconds)
                
                # Run backup
                await self.run_backup()
                
            except asyncio.CancelledError:
                break
            except Exception as e:
                logger.error(f"Backup scheduler error: {e}")
                await asyncio.sleep(3600)  # Wait 1 hour before retry
    
    async def run_backup(self, format: str = "json") -> Dict:
        """Run a backup now."""
        from db import get_telemetry_db
        
        logger.info("Starting backup...")
        
        start_time = datetime.now()
        date_str = start_time.strftime("%Y-%m-%d")
        
        # Calculate date range (last 24 hours)
        end_ts = int(start_time.timestamp())
        start_ts = end_ts - 86400
        
        result = {
            "date": date_str,
            "started_at": start_time.isoformat(),
            "status": "running",
            "files": [],
            "errors": []
        }
        
        try:
            db = await get_telemetry_db()
            
            # Export telemetry data
            telemetry_file = await self._export_telemetry(db, date_str, start_ts, end_ts, format)
            if telemetry_file:
                result["files"].append({"type": "telemetry", "path": str(telemetry_file)})
            
            # Export IoT data
            iot_file = await self._export_iot(db, date_str, start_ts, end_ts, format)
            if iot_file:
                result["files"].append({"type": "iot", "path": str(iot_file)})
            
            # Upload to Google Drive if configured
            if self.is_authenticated():
                for file_info in result["files"]:
                    try:
                        file_id = await self._upload_to_gdrive(Path(file_info["path"]))
                        file_info["gdrive_id"] = file_id
                        file_info["uploaded"] = True
                    except Exception as e:
                        file_info["uploaded"] = False
                        file_info["error"] = str(e)
                        result["errors"].append(f"Upload failed for {file_info['type']}: {e}")
            
            result["status"] = "completed" if not result["errors"] else "completed_with_errors"
            
        except Exception as e:
            logger.error(f"Backup failed: {e}")
            result["status"] = "failed"
            result["errors"].append(str(e))
        
        result["completed_at"] = datetime.now().isoformat()
        result["duration_seconds"] = (datetime.now() - start_time).total_seconds()
        
        self.last_backup = result
        self.backup_history.append(result)
        
        # Keep only last 30 backup records in memory
        if len(self.backup_history) > 30:
            self.backup_history = self.backup_history[-30:]
        
        logger.info(f"Backup completed: {result['status']}")
        return result
    
    async def _export_telemetry(self, db, date_str: str, start_ts: int, end_ts: int, format: str) -> Optional[Path]:
        """Export telemetry data to file."""
        cursor = await db.execute("""
            SELECT ts, metric, labels_json, value 
            FROM metrics_raw 
            WHERE ts >= ? AND ts < ?
            ORDER BY ts
        """, (start_ts, end_ts))
        
        rows = await cursor.fetchall()
        
        if not rows:
            logger.info("No telemetry data to export")
            return None
        
        filename = f"backup_{date_str}_telemetry.{format}"
        filepath = self.backup_dir / filename
        
        if format == "json":
            data = []
            for row in rows:
                data.append({
                    "timestamp": row[0],
                    "datetime": datetime.fromtimestamp(row[0]).isoformat(),
                    "metric": row[1],
                    "labels": json.loads(row[2]) if row[2] else {},
                    "value": row[3]
                })
            
            async with aiofiles.open(filepath, 'w') as f:
                await f.write(json.dumps(data, indent=2, ensure_ascii=False))
        
        elif format == "csv":
            with open(filepath, 'w', newline='') as f:
                writer = csv.writer(f)
                writer.writerow(["timestamp", "datetime", "metric", "labels", "value"])
                for row in rows:
                    writer.writerow([
                        row[0],
                        datetime.fromtimestamp(row[0]).isoformat(),
                        row[1],
                        row[2],
                        row[3]
                    ])
        
        logger.info(f"Exported {len(rows)} telemetry records to {filename}")
        return filepath
    
    async def _export_iot(self, db, date_str: str, start_ts: int, end_ts: int, format: str) -> Optional[Path]:
        """Export IoT sensor data to file."""
        cursor = await db.execute("""
            SELECT device_id, sensor_type, value, unit, timestamp 
            FROM iot_sensor_readings 
            WHERE timestamp >= ? AND timestamp < ?
            ORDER BY timestamp
        """, (start_ts, end_ts))
        
        rows = await cursor.fetchall()
        
        if not rows:
            logger.info("No IoT data to export")
            return None
        
        filename = f"backup_{date_str}_iot.{format}"
        filepath = self.backup_dir / filename
        
        if format == "json":
            data = []
            for row in rows:
                data.append({
                    "device_id": row[0],
                    "sensor_type": row[1],
                    "value": row[2],
                    "unit": row[3],
                    "timestamp": row[4],
                    "datetime": datetime.fromtimestamp(row[4]).isoformat()
                })
            
            async with aiofiles.open(filepath, 'w') as f:
                await f.write(json.dumps(data, indent=2, ensure_ascii=False))
        
        elif format == "csv":
            with open(filepath, 'w', newline='') as f:
                writer = csv.writer(f)
                writer.writerow(["device_id", "sensor_type", "value", "unit", "timestamp", "datetime"])
                for row in rows:
                    writer.writerow([
                        row[0], row[1], row[2], row[3], row[4],
                        datetime.fromtimestamp(row[4]).isoformat()
                    ])
        
        logger.info(f"Exported {len(rows)} IoT records to {filename}")
        return filepath
    
    async def _upload_to_gdrive(self, filepath: Path) -> str:
        """Upload a file to Google Drive."""
        if not self.service:
            raise Exception("Google Drive not authenticated")
        
        file_metadata = {
            'name': filepath.name,
            'parents': [self.folder_id] if self.folder_id else []
        }
        
        media = MediaFileUpload(str(filepath), resumable=True)
        
        file = self.service.files().create(
            body=file_metadata,
            media_body=media,
            fields='id'
        ).execute()
        
        logger.info(f"Uploaded {filepath.name} to Google Drive (ID: {file.get('id')})")
        return file.get('id')
    
    def get_status(self) -> Dict:
        """Get current backup service status."""
        return {
            "gdrive_available": GDRIVE_AVAILABLE,
            "configured": self.is_configured(),
            "authenticated": self.is_authenticated(),
            "scheduler_running": self._running,
            "last_backup": self.last_backup,
            "backup_directory": str(self.backup_dir),
            "local_backups": self._get_local_backups()
        }
    
    def _get_local_backups(self) -> List[Dict]:
        """Get list of local backup files."""
        backups = []
        if self.backup_dir.exists():
            for f in sorted(self.backup_dir.glob("backup_*"), reverse=True)[:20]:
                backups.append({
                    "filename": f.name,
                    "size_bytes": f.stat().st_size,
                    "modified": datetime.fromtimestamp(f.stat().st_mtime).isoformat()
                })
        return backups


# Global instance
backup_service = GDriveBackupService()
