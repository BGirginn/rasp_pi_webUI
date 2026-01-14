"""
Pi Control Panel - Database Migrations

Handles schema migrations and initial data setup.
"""

import asyncio
import os
import secrets
from datetime import datetime

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
    await db.execute("CREATE INDEX IF NOT EXISTS idx_alerts_state ON alerts(state)")
    await db.execute("CREATE INDEX IF NOT EXISTS idx_alerts_rule ON alerts(rule_id)")


async def migrate_002_default_admin(db):
    """Create default admin user if none exists."""
    cursor = await db.execute("SELECT COUNT(*) FROM users WHERE role = 'admin'")
    count = (await cursor.fetchone())[0]
    
    if count == 0:
        # Generate random password
        default_password = os.environ.get("DEFAULT_ADMIN_PASSWORD", "admin123")
        password_hash = hash_password(default_password)
        
        await db.execute(
            """INSERT INTO users (username, password_hash, role, email)
               VALUES (?, ?, ?, ?)""",
            ("admin", password_hash, "admin", "admin@localhost")
        )
        
        print(f"  Created default admin user: admin")
        print(f"  Default password: {default_password}")
        print(f"  ⚠️  CHANGE THIS PASSWORD IMMEDIATELY!")


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
    """Create default standard user if none exists."""
    cursor = await db.execute("SELECT COUNT(*) FROM users WHERE username = 'user'")
    count = (await cursor.fetchone())[0]
    
    if count == 0:
        # Default standard user
        default_password = "user123"
        password_hash = hash_password(default_password)
        
        await db.execute(
            """INSERT INTO users (username, password_hash, role)
               VALUES (?, ?, ?)""",
            ("user", password_hash, "viewer")
        )
        
        print(f"  Created default standard user: user")
        print(f"  Role: viewer")


if __name__ == "__main__":
    import sys
    db_path = sys.argv[1] if len(sys.argv) > 1 else "/data/control.db"
    asyncio.run(run_migrations(db_path))
