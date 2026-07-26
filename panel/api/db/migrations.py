"""
Pi Control Panel - Database Migrations

Handles schema migrations and initial data setup.
"""

import asyncio
import os

import aiosqlite
import bcrypt

def hash_password(password: str) -> str:
    """Hash a password using bcrypt."""
    return bcrypt.hashpw(password.encode(), bcrypt.gensalt()).decode()


async def run_migrations(db_path: str):
    """Run all pending migrations."""
    async with aiosqlite.connect(db_path) as db:
        # Create migrations tracking table
        await db.execute("""
            CREATE TABLE IF NOT EXISTS migrations (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                name TEXT UNIQUE NOT NULL,
                applied_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
            )
        """)
        await db.commit()
        
        # Get applied migrations
        cursor = await db.execute("SELECT name FROM migrations")
        applied = {row[0] for row in await cursor.fetchall()}
        
        # Define migrations
        migrations = [
            ("001_initial_schema", migrate_001_initial_schema),
            ("002_default_admin", migrate_002_default_admin),
            ("003_ignored_resources", migrate_003_ignored_resources),
            ("004_alert_history", migrate_004_alert_history),
            ("005_standard_user", migrate_005_standard_user),
            ("006_login_lockout", migrate_006_login_lockout),
            ("007_operations_foundation", migrate_007_operations_foundation),
        ]
        
        # Apply pending migrations
        for name, func in migrations:
            if name not in applied:
                print(f"Applying migration: {name}")
                await func(db)
                await db.execute("INSERT INTO migrations (name) VALUES (?)", (name,))
                await db.commit()
                print(f"  ✓ {name} applied")


async def migrate_001_initial_schema(db):
    """Initial database schema."""
    # Users table
    await db.execute("""
        CREATE TABLE IF NOT EXISTS users (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            username TEXT UNIQUE NOT NULL,
            password_hash TEXT NOT NULL,
            role TEXT NOT NULL CHECK (role IN ('admin', 'operator', 'viewer')),
            totp_secret TEXT,
            email TEXT,
            created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
            updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
            last_login TIMESTAMP
        )
    """)
    
    # Sessions table
    await db.execute("""
        CREATE TABLE IF NOT EXISTS sessions (
            id TEXT PRIMARY KEY,
            user_id INTEGER NOT NULL,
            refresh_token_hash TEXT NOT NULL,
            device_info TEXT,
            ip_address TEXT,
            expires_at TIMESTAMP NOT NULL,
            created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
            FOREIGN KEY (user_id) REFERENCES users(id) ON DELETE CASCADE
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
            metadata_json TEXT,
            discovered_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
            updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
        )
    """)
    
    # Manifests table
    await db.execute("""
        CREATE TABLE IF NOT EXISTS manifests (
            id TEXT PRIMARY KEY,
            resource_id TEXT NOT NULL,
            name TEXT NOT NULL,
            version TEXT,
            config_json TEXT NOT NULL,
            approved_by INTEGER,
            approved_at TIMESTAMP,
            created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
            FOREIGN KEY (resource_id) REFERENCES resources(id),
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
            resource_type TEXT,
            details TEXT,
            result TEXT,
            ip_address TEXT,
            user_agent TEXT,
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
            config_json TEXT,
            result_json TEXT,
            error TEXT,
            progress INTEGER DEFAULT 0,
            started_by INTEGER,
            started_at TIMESTAMP,
            completed_at TIMESTAMP,
            created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
            FOREIGN KEY (started_by) REFERENCES users(id)
        )
    """)
    
    # Job logs table
    await db.execute("""
        CREATE TABLE IF NOT EXISTS job_logs (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            job_id TEXT NOT NULL,
            level TEXT NOT NULL,
            message TEXT NOT NULL,
            created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
            FOREIGN KEY (job_id) REFERENCES jobs(id) ON DELETE CASCADE
        )
    """)
    
    # Alert rules table
    await db.execute("""
        CREATE TABLE IF NOT EXISTS alert_rules (
            id TEXT PRIMARY KEY,
            name TEXT NOT NULL,
            description TEXT,
            metric TEXT NOT NULL,
            condition TEXT NOT NULL,
            threshold REAL NOT NULL,
            severity TEXT NOT NULL CHECK (severity IN ('info', 'warning', 'critical')),
            cooldown_minutes INTEGER DEFAULT 15,
            enabled INTEGER DEFAULT 1,
            notify_channels TEXT,
            created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
            updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
        )
    """)
    
    # Active alerts table
    await db.execute("""
        CREATE TABLE IF NOT EXISTS alerts (
            id TEXT PRIMARY KEY,
            rule_id TEXT NOT NULL,
            state TEXT NOT NULL CHECK (state IN ('pending', 'firing', 'resolved', 'acknowledged')),
            severity TEXT NOT NULL,
            message TEXT,
            value REAL,
            fired_at TIMESTAMP,
            resolved_at TIMESTAMP,
            acknowledged_by INTEGER,
            acknowledged_at TIMESTAMP,
            created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
            FOREIGN KEY (rule_id) REFERENCES alert_rules(id),
            FOREIGN KEY (acknowledged_by) REFERENCES users(id)
        )
    """)
    
    # Settings table (key-value store)
    await db.execute("""
        CREATE TABLE IF NOT EXISTS settings (
            key TEXT PRIMARY KEY,
            value TEXT NOT NULL,
            updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
        )
    """)
    
    # Create indexes
    await db.execute("CREATE INDEX IF NOT EXISTS idx_sessions_user ON sessions(user_id)")
    await db.execute("CREATE INDEX IF NOT EXISTS idx_sessions_expires ON sessions(expires_at)")
    await db.execute("CREATE INDEX IF NOT EXISTS idx_resources_provider ON resources(provider)")
    await db.execute("CREATE INDEX IF NOT EXISTS idx_resources_class ON resources(class)")
    await db.execute("CREATE INDEX IF NOT EXISTS idx_audit_log_user ON audit_log(user_id)")
    await db.execute("CREATE INDEX IF NOT EXISTS idx_audit_log_created ON audit_log(created_at)")
    await db.execute("CREATE INDEX IF NOT EXISTS idx_audit_log_action ON audit_log(action)")
    await db.execute("CREATE INDEX IF NOT EXISTS idx_jobs_state ON jobs(state)")
    await db.execute("CREATE INDEX IF NOT EXISTS idx_jobs_type ON jobs(type)")
    await db.execute("CREATE INDEX IF NOT EXISTS idx_job_logs_job_id ON job_logs(job_id)")
    await db.execute("CREATE INDEX IF NOT EXISTS idx_job_logs_job_created ON job_logs(job_id, created_at)")
    await db.execute("CREATE INDEX IF NOT EXISTS idx_alerts_state ON alerts(state)")
    await db.execute("CREATE INDEX IF NOT EXISTS idx_alerts_rule ON alerts(rule_id)")


async def migrate_002_default_admin(db):
    """Create default admin user if none exists."""
    cursor = await db.execute("SELECT COUNT(*) FROM users WHERE role = 'admin'")
    count = (await cursor.fetchone())[0]
    
    if count == 0:
        default_password = os.environ.get("DEFAULT_ADMIN_PASSWORD")
        if not default_password:
            raise RuntimeError(
                "DEFAULT_ADMIN_PASSWORD is required when creating the initial admin"
            )
        password_hash = hash_password(default_password)
        
        await db.execute(
            """INSERT INTO users (username, password_hash, role, email)
               VALUES (?, ?, ?, ?)""",
            ("admin", password_hash, "admin", "admin@localhost")
        )
        
        print("  Created default admin user: admin")
        print("  ⚠️  CHANGE THIS PASSWORD IMMEDIATELY!")


async def migrate_003_ignored_resources(db):
    """Add ignored resources table."""
    await db.execute("""
        CREATE TABLE IF NOT EXISTS ignored_resources (
            resource_id TEXT PRIMARY KEY,
            reason TEXT,
            ignored_by INTEGER,
            ignored_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
            FOREIGN KEY (ignored_by) REFERENCES users(id)
        )
    """)


async def migrate_004_alert_history(db):
    """Add alert history for retention."""
    await db.execute("""
        CREATE TABLE IF NOT EXISTS alert_history (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            alert_id TEXT NOT NULL,
            rule_id TEXT NOT NULL,
            rule_name TEXT,
            severity TEXT NOT NULL,
            message TEXT,
            value REAL,
            fired_at TIMESTAMP,
            resolved_at TIMESTAMP,
            duration_seconds INTEGER,
            created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
        )
    """)
    
    await db.execute("CREATE INDEX IF NOT EXISTS idx_alert_history_created ON alert_history(created_at)")
    await db.execute("CREATE INDEX IF NOT EXISTS idx_alert_history_rule ON alert_history(rule_id)")


async def migrate_005_standard_user(db):
    """Retained migration marker; predictable default viewer accounts are unsafe."""


async def migrate_006_login_lockout(db):
    """Add login failure tracking for account lockout."""
    cursor = await db.execute("PRAGMA table_info(users)")
    columns = {row[1] for row in await cursor.fetchall()}

    if "failed_login_count" not in columns:
        await db.execute("ALTER TABLE users ADD COLUMN failed_login_count INTEGER DEFAULT 0")

    if "locked_until" not in columns:
        await db.execute("ALTER TABLE users ADD COLUMN locked_until TIMESTAMP")


async def _add_column_if_missing(db, table: str, column: str, definition: str):
    cursor = await db.execute(f"PRAGMA table_info({table})")
    existing = {row[1] for row in await cursor.fetchall()}
    if column not in existing:
        await db.execute(f"ALTER TABLE {table} ADD COLUMN {column} {definition}")


async def migrate_007_operations_foundation(db):
    """Add durable operations, provisioning, project, and audit metadata."""
    for column, definition in (
        ("phase", "TEXT"),
        ("cancellable", "INTEGER NOT NULL DEFAULT 1"),
        ("checkpoint_json", "TEXT"),
        ("updated_at", "TIMESTAMP"),
    ):
        await _add_column_if_missing(db, "jobs", column, definition)

    for column, definition in (
        ("family_id", "TEXT"),
        ("parent_id", "TEXT"),
        ("last_used_at", "TIMESTAMP"),
        ("revoked_at", "TIMESTAMP"),
        ("ip_address", "TEXT"),
    ):
        await _add_column_if_missing(db, "sessions", column, definition)

    for column in ("previous_hash", "event_hash"):
        await _add_column_if_missing(db, "audit_log", column, "TEXT")

    await db.executescript(
        """
        CREATE TABLE IF NOT EXISTS job_schedules (
            id TEXT PRIMARY KEY,
            name TEXT NOT NULL,
            job_type TEXT NOT NULL,
            config_json TEXT,
            cron_expression TEXT NOT NULL,
            timezone TEXT NOT NULL DEFAULT 'Europe/Istanbul',
            enabled INTEGER NOT NULL DEFAULT 1,
            next_run_at TIMESTAMP,
            last_run_at TIMESTAMP,
            created_by INTEGER,
            created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
            updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
            FOREIGN KEY (created_by) REFERENCES users(id)
        );

        CREATE TABLE IF NOT EXISTS restore_points (
            id TEXT PRIMARY KEY,
            filename TEXT NOT NULL,
            source TEXT NOT NULL,
            manifest_json TEXT NOT NULL,
            checksum TEXT NOT NULL,
            size_bytes INTEGER NOT NULL,
            status TEXT NOT NULL,
            created_by INTEGER,
            created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
            FOREIGN KEY (created_by) REFERENCES users(id)
        );

        CREATE TABLE IF NOT EXISTS notifications (
            id TEXT PRIMARY KEY,
            kind TEXT NOT NULL,
            severity TEXT NOT NULL,
            title TEXT NOT NULL,
            message TEXT NOT NULL,
            dedupe_key TEXT,
            resource_id TEXT,
            read_at TIMESTAMP,
            resolved_at TIMESTAMP,
            created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
        );

        CREATE TABLE IF NOT EXISTS notification_deliveries (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            notification_id TEXT NOT NULL,
            channel TEXT NOT NULL,
            state TEXT NOT NULL,
            attempts INTEGER NOT NULL DEFAULT 0,
            last_error TEXT,
            next_attempt_at TIMESTAMP,
            delivered_at TIMESTAMP,
            created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
            FOREIGN KEY (notification_id) REFERENCES notifications(id) ON DELETE CASCADE
        );

        CREATE TABLE IF NOT EXISTS mqtt_devices (
            id TEXT PRIMARY KEY,
            name TEXT NOT NULL,
            username TEXT UNIQUE NOT NULL,
            status TEXT NOT NULL DEFAULT 'provisioned',
            last_seen_at TIMESTAMP,
            credential_rotated_at TIMESTAMP,
            created_by INTEGER,
            created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
            FOREIGN KEY (created_by) REFERENCES users(id)
        );

        CREATE TABLE IF NOT EXISTS projects (
            id TEXT PRIMARY KEY,
            name TEXT NOT NULL,
            root_path TEXT UNIQUE NOT NULL,
            project_type TEXT NOT NULL DEFAULT 'directory',
            excludes_json TEXT,
            enabled INTEGER NOT NULL DEFAULT 1,
            created_by INTEGER,
            created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
            updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
            FOREIGN KEY (created_by) REFERENCES users(id)
        );

        CREATE TABLE IF NOT EXISTS project_snapshots (
            id TEXT PRIMARY KEY,
            project_id TEXT NOT NULL,
            filename TEXT NOT NULL,
            checksum TEXT NOT NULL,
            size_bytes INTEGER NOT NULL,
            manifest_json TEXT NOT NULL,
            created_by INTEGER,
            created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
            FOREIGN KEY (project_id) REFERENCES projects(id) ON DELETE CASCADE,
            FOREIGN KEY (created_by) REFERENCES users(id)
        );

        CREATE INDEX IF NOT EXISTS idx_jobs_updated ON jobs(updated_at);
        CREATE INDEX IF NOT EXISTS idx_job_schedules_next ON job_schedules(enabled, next_run_at);
        CREATE INDEX IF NOT EXISTS idx_notifications_unread ON notifications(read_at, created_at);
        CREATE UNIQUE INDEX IF NOT EXISTS idx_notifications_dedupe_active
            ON notifications(dedupe_key) WHERE dedupe_key IS NOT NULL AND resolved_at IS NULL;
        CREATE INDEX IF NOT EXISTS idx_notification_deliveries_retry
            ON notification_deliveries(state, next_attempt_at);
        CREATE INDEX IF NOT EXISTS idx_project_snapshots_project
            ON project_snapshots(project_id, created_at);
        CREATE INDEX IF NOT EXISTS idx_sessions_family ON sessions(family_id);
        CREATE INDEX IF NOT EXISTS idx_audit_event_hash ON audit_log(event_hash);
        """
    )


if __name__ == "__main__":
    import sys
    db_path = sys.argv[1] if len(sys.argv) > 1 else "/data/control.db"
    asyncio.run(run_migrations(db_path))
