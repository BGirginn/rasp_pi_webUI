"""
Pi Control Panel - Database Module

SQLite database initialization and utilities.
"""

import aiosqlite
import structlog

from config import settings

logger = structlog.get_logger(__name__)

# Database connections
_control_db = None
_telemetry_db = None


async def init_db():
    """Initialize database connections and schema."""
    global _control_db, _telemetry_db
    
    # Initialize control database
    _control_db = await aiosqlite.connect(settings.database_path)
    await _control_db.execute("PRAGMA journal_mode=WAL")
    await _control_db.execute("PRAGMA synchronous=NORMAL")
    await _init_control_schema(_control_db)
    logger.info("Control database initialized", path=settings.database_path)
    
    # Initialize telemetry database
    _telemetry_db = await aiosqlite.connect(settings.telemetry_db_path)
    await _telemetry_db.execute("PRAGMA journal_mode=WAL")
    await _telemetry_db.execute("PRAGMA synchronous=NORMAL")
    await _init_telemetry_schema(_telemetry_db)
    logger.info("Telemetry database initialized", path=settings.telemetry_db_path)


async def close_db():
    """Close database connections."""
    global _control_db, _telemetry_db
    
    if _control_db:
        await _control_db.close()
        _control_db = None
    
    if _telemetry_db:
        await _telemetry_db.close()
        _telemetry_db = None
    
    logger.info("Database connections closed")


async def get_control_db():
    """Get control database connection."""
    if not _control_db:
        raise RuntimeError("Database not initialized")
    return _control_db


async def get_telemetry_db():
    """Get telemetry database connection."""
    if not _telemetry_db:
        raise RuntimeError("Database not initialized")
    return _telemetry_db


async def _init_control_schema(db):
    """Initialize control database schema."""
    
    # Users table
    await db.execute("""
        CREATE TABLE IF NOT EXISTS users (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            username TEXT UNIQUE NOT NULL,
            password_hash TEXT NOT NULL,
            role TEXT NOT NULL CHECK (role IN ('admin', 'operator', 'viewer')),
            totp_secret TEXT,
            created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
            updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
        )
    """)
    
    # Sessions table
    await db.execute("""
        CREATE TABLE IF NOT EXISTS sessions (
            id TEXT PRIMARY KEY,
            user_id INTEGER NOT NULL,
            refresh_token_hash TEXT NOT NULL,
            device_info TEXT,
            expires_at TIMESTAMP NOT NULL,
            created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
            FOREIGN KEY (user_id) REFERENCES users(id)
        )
    """)
    
    # Resources table
    await db.execute("""
        CREATE TABLE IF NOT EXISTS resources (
            id TEXT PRIMARY KEY,
            name TEXT NOT NULL,
            type TEXT NOT NULL,
            class TEXT NOT NULL CHECK (class IN ('CORE', 'SYSTEM', 'APP', 'DEVICE')),
            provider TEXT NOT NULL,
            state TEXT NOT NULL,
            health_score INTEGER DEFAULT 0,
            manifest_id TEXT,
            managed INTEGER DEFAULT 0,
            discovered_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
            updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
        )
    """)
    
    # Manifests table
    await db.execute("""
        CREATE TABLE IF NOT EXISTS manifests (
            id TEXT PRIMARY KEY,
            resource_id TEXT NOT NULL,
            config TEXT NOT NULL,
            approved_by INTEGER,
            approved_at TIMESTAMP,
            created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
            FOREIGN KEY (approved_by) REFERENCES users(id)
        )
    """)
    
    # Audit log table
    await db.execute("""
        CREATE TABLE IF NOT EXISTS audit_log (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            user_id INTEGER,
            action TEXT NOT NULL,
            resource_id TEXT,
            details TEXT,
            result TEXT,
            ip_address TEXT,
            created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
        )
    """)
    
    # Jobs table
    await db.execute("""
        CREATE TABLE IF NOT EXISTS jobs (
            id TEXT PRIMARY KEY,
            name TEXT NOT NULL,
            type TEXT NOT NULL,
            state TEXT NOT NULL CHECK (state IN ('pending', 'running', 'completed', 'failed', 'rolled_back', 'cancelled')),
            config TEXT,
            result TEXT,
            error TEXT,
            started_at TIMESTAMP,
            completed_at TIMESTAMP,
            created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
        )
    """)
    
    # Alert rules table
    await db.execute("""
        CREATE TABLE IF NOT EXISTS alert_rules (
            id TEXT PRIMARY KEY,
            name TEXT NOT NULL,
            metric TEXT NOT NULL,
            condition TEXT NOT NULL,
            severity TEXT NOT NULL,
            cooldown_minutes INTEGER DEFAULT 15,
            enabled INTEGER DEFAULT 1,
            created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
        )
    """)
    
    # Active alerts table
    await db.execute("""
        CREATE TABLE IF NOT EXISTS alerts (
            id TEXT PRIMARY KEY,
            rule_id TEXT NOT NULL,
            state TEXT NOT NULL CHECK (state IN ('pending', 'firing', 'resolved', 'acknowledged')),
            message TEXT,
            fired_at TIMESTAMP,
            resolved_at TIMESTAMP,
            acknowledged_by INTEGER,
            created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
            FOREIGN KEY (rule_id) REFERENCES alert_rules(id),
            FOREIGN KEY (acknowledged_by) REFERENCES users(id)
        )
    """)
    
    # Create indexes
    await db.execute("CREATE INDEX IF NOT EXISTS idx_sessions_user ON sessions(user_id)")
    await db.execute("CREATE INDEX IF NOT EXISTS idx_resources_provider ON resources(provider)")
    await db.execute("CREATE INDEX IF NOT EXISTS idx_audit_log_user ON audit_log(user_id)")
    await db.execute("CREATE INDEX IF NOT EXISTS idx_audit_log_created ON audit_log(created_at)")
    await db.execute("CREATE INDEX IF NOT EXISTS idx_jobs_state ON jobs(state)")
    await db.execute("CREATE INDEX IF NOT EXISTS idx_alerts_state ON alerts(state)")
    
    await db.commit()


async def _init_telemetry_schema(db):
    """Initialize telemetry database schema."""
    
    # Raw metrics table
    await db.execute("""
        CREATE TABLE IF NOT EXISTS metrics_raw (
            ts INTEGER NOT NULL,
            metric TEXT NOT NULL,
            labels_json TEXT,
            value REAL NOT NULL
        )
    """)
    
    # Summary metrics table
    await db.execute("""
        CREATE TABLE IF NOT EXISTS metrics_summary (
            ts INTEGER NOT NULL,
            metric TEXT NOT NULL,
            labels_json TEXT,
            avg REAL,
            min REAL,
            max REAL,
            p50 REAL,
            p95 REAL,
            p99 REAL,
            count INTEGER
        )
    """)
    
    # Create indexes
    await db.execute("CREATE INDEX IF NOT EXISTS idx_metrics_raw_lookup ON metrics_raw(metric, ts)")
    await db.execute("CREATE INDEX IF NOT EXISTS idx_metrics_summary_lookup ON metrics_summary(metric, ts)")
    
    await db.commit()
