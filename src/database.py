"""
SQLite Database Manager for Galatea Cloud.

Provides async database operations using aiosqlite.
Handles users, sessions, and activity logging in a single database.
"""

import aiosqlite
import logging
import json
from datetime import datetime, timedelta
from pathlib import Path
from typing import Optional, Any

logger = logging.getLogger(__name__)

# Allowed columns for each table (security: prevents SQL injection via dynamic column names)
# Reference: OWASP SQL Injection Prevention Cheat Sheet - Defense Option 3 (Allow-list Validation)
USERS_COLUMNS = frozenset(
    {
        "user_id",
        "username",
        "language",
        "is_vip",
        "is_banned",
        "banned_at",
        "request_count",
        "request_month",
        "first_request_at",
        "last_request_at",
        "created_at",
        "updated_at",
    }
)

SESSIONS_COLUMNS = frozenset(
    {
        "user_id",
        "state",
        "language",
        "file_name",
        "file_type",
        "file_content",
        "file_path",
        "pending_content",
        "pending_doc_type",
        "pending_template",
        "conversation_history",
        "todos",
        "preview_pages",
        "preview_current_page",
        "current_sheet",
        "current_cell",
        "current_slide_index",
        "content_hash",
        "cached_analysis_hash",
        "cached_translation",
        "cached_summary_hash",
        "cached_summary",
        "last_activity",
        "created_at",
    }
)


class Database:
    """
    Async SQLite database manager.

    Singleton pattern ensures only one connection pool is used.
    """

    _instance: Optional["Database"] = None
    _db: Optional[aiosqlite.Connection] = None
    _db_path: Optional[Path] = None
    _initialized: bool = False

    def __new__(cls):
        if cls._instance is None:
            cls._instance = super().__new__(cls)
        return cls._instance

    @staticmethod
    def _validate_columns(columns: set, allowed: frozenset, table: str) -> None:
        """
        Validate that all column names are in the allowed whitelist.

        This prevents SQL injection through dynamic column names.
        Reference: OWASP SQL Injection Prevention - Defense Option 3 (Allow-list Validation)

        Args:
            columns: Column names to validate
            allowed: Allowed column names for the table
            table: Table name (for error message)

        Raises:
            ValueError: If any column is not in the whitelist
        """
        invalid = columns - allowed
        if invalid:
            raise ValueError(
                f"Invalid column(s) for {table} table: {invalid}. "
                f"Allowed columns: {sorted(allowed)}"
            )

    @classmethod
    async def init(cls, db_path: Path) -> "Database":
        """
        Initialize the database connection and create tables.

        Args:
            db_path: Path to the SQLite database file

        Returns:
            Database instance
        """
        instance = cls()

        if instance._initialized and instance._db_path == db_path:
            return instance

        # Close existing connection if path changed
        if instance._db:
            await instance.close()

        instance._db_path = db_path

        # Ensure directory exists
        db_path.parent.mkdir(parents=True, exist_ok=True)

        # Open connection
        instance._db = await aiosqlite.connect(str(db_path))
        instance._db.row_factory = aiosqlite.Row

        # Enable WAL mode for better concurrency
        await instance._db.execute("PRAGMA journal_mode=WAL")
        await instance._db.execute("PRAGMA busy_timeout=5000")

        # Create tables
        await instance._create_tables()

        instance._initialized = True
        logger.info(f"Database initialized at {db_path}")

        return instance

    @classmethod
    def get_instance(cls) -> "Database":
        """Get the singleton instance."""
        if cls._instance is None or not cls._instance._initialized:
            raise RuntimeError("Database not initialized. Call Database.init() first.")
        return cls._instance

    async def _create_tables(self) -> None:
        """Create database tables if they don't exist."""

        # Users table - combines rate_limits, vip, banned
        await self._db.execute("""
            CREATE TABLE IF NOT EXISTS users (
                user_id INTEGER PRIMARY KEY,
                username TEXT,
                language TEXT DEFAULT 'en',
                is_vip INTEGER DEFAULT 0,
                is_banned INTEGER DEFAULT 0,
                banned_at TEXT,
                request_count INTEGER DEFAULT 0,
                request_month TEXT,
                first_request_at TEXT,
                last_request_at TEXT,
                created_at TEXT DEFAULT CURRENT_TIMESTAMP,
                updated_at TEXT DEFAULT CURRENT_TIMESTAMP
            )
        """)

        # Sessions table
        await self._db.execute("""
            CREATE TABLE IF NOT EXISTS sessions (
                user_id INTEGER PRIMARY KEY,
                state TEXT DEFAULT 'IDLE',
                language TEXT DEFAULT 'en',
                file_name TEXT,
                file_type TEXT,
                file_content TEXT,
                file_path TEXT,
                pending_content TEXT,
                pending_doc_type TEXT,
                pending_template TEXT,
                conversation_history TEXT,
                todos TEXT,
                preview_pages TEXT,
                preview_current_page INTEGER DEFAULT 0,
                current_sheet TEXT,
                current_cell TEXT,
                current_slide_index INTEGER,
                content_hash TEXT,
                cached_analysis_hash TEXT,
                cached_translation TEXT,
                cached_summary_hash TEXT,
                cached_summary TEXT,
                last_activity TEXT,
                created_at TEXT DEFAULT CURRENT_TIMESTAMP
            )
        """)

        # Activity log table
        await self._db.execute("""
            CREATE TABLE IF NOT EXISTS activity_log (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                timestamp TEXT DEFAULT CURRENT_TIMESTAMP,
                user_id INTEGER,
                username TEXT,
                action TEXT NOT NULL,
                details TEXT
            )
        """)

        # Create indexes for better query performance
        await self._db.execute("""
            CREATE INDEX IF NOT EXISTS idx_activity_timestamp 
            ON activity_log(timestamp DESC)
        """)

        await self._db.execute("""
            CREATE INDEX IF NOT EXISTS idx_activity_user 
            ON activity_log(user_id)
        """)

        await self._db.execute("""
            CREATE INDEX IF NOT EXISTS idx_sessions_activity 
            ON sessions(last_activity)
        """)

        await self._db.commit()
        logger.debug("Database tables created/verified")

    async def close(self) -> None:
        """Close the database connection."""
        if self._db:
            await self._db.close()
            self._db = None
            self._initialized = False
            logger.info("Database connection closed")

    # ==================== User Operations ====================

    async def get_user(self, user_id: int) -> Optional[dict]:
        """
        Get a user by ID.

        Args:
            user_id: Telegram user ID

        Returns:
            User dict or None if not found
        """
        async with self._db.execute(
            "SELECT * FROM users WHERE user_id = ?", (user_id,)
        ) as cursor:
            row = await cursor.fetchone()
            if row:
                return dict(row)
            return None

    async def upsert_user(self, user_id: int, **kwargs) -> dict:
        """
        Insert or update a user.

        Args:
            user_id: Telegram user ID
            **kwargs: Fields to update

        Returns:
            Updated user dict
        """
        # Validate column names against whitelist (prevents SQL injection)
        if kwargs:
            self._validate_columns(set(kwargs.keys()), USERS_COLUMNS, "users")

        existing = await self.get_user(user_id)

        if existing:
            # Update existing user
            if kwargs:
                kwargs["updated_at"] = datetime.utcnow().isoformat()
                set_clause = ", ".join(f"{k} = ?" for k in kwargs.keys())
                values = list(kwargs.values()) + [user_id]

                await self._db.execute(
                    f"UPDATE users SET {set_clause} WHERE user_id = ?", values
                )
                await self._db.commit()
        else:
            # Insert new user
            kwargs["user_id"] = user_id
            kwargs["created_at"] = datetime.utcnow().isoformat()
            kwargs["updated_at"] = kwargs["created_at"]

            columns = ", ".join(kwargs.keys())
            placeholders = ", ".join("?" * len(kwargs))

            await self._db.execute(
                f"INSERT INTO users ({columns}) VALUES ({placeholders})",
                list(kwargs.values()),
            )
            await self._db.commit()

        return await self.get_user(user_id)

    async def get_all_users(self) -> list[dict]:
        """Get all users."""
        async with self._db.execute("SELECT * FROM users") as cursor:
            rows = await cursor.fetchall()
            return [dict(row) for row in rows]

    async def get_all_user_ids(self) -> list[int]:
        """Get all user IDs."""
        async with self._db.execute("SELECT user_id FROM users") as cursor:
            rows = await cursor.fetchall()
            return [row["user_id"] for row in rows]

    async def delete_user(self, user_id: int) -> bool:
        """Delete a user and their session."""
        await self._db.execute("DELETE FROM users WHERE user_id = ?", (user_id,))
        await self._db.execute("DELETE FROM sessions WHERE user_id = ?", (user_id,))
        await self._db.commit()
        return True

    async def get_user_stats(self) -> dict:
        """Get user statistics."""
        current_month = datetime.utcnow().strftime("%Y-%m")

        async with self._db.execute("SELECT COUNT(*) as count FROM users") as cursor:
            total = (await cursor.fetchone())["count"]

        async with self._db.execute(
            "SELECT COUNT(*) as count FROM users WHERE is_vip = 1"
        ) as cursor:
            vip_count = (await cursor.fetchone())["count"]

        async with self._db.execute(
            "SELECT COUNT(*) as count FROM users WHERE is_banned = 1"
        ) as cursor:
            banned_count = (await cursor.fetchone())["count"]

        async with self._db.execute(
            "SELECT SUM(request_count) as total FROM users WHERE request_month = ?",
            (current_month,),
        ) as cursor:
            row = await cursor.fetchone()
            total_requests = row["total"] or 0

        # Top users this month
        async with self._db.execute(
            """SELECT user_id, username, request_count, is_vip 
               FROM users 
               WHERE request_month = ? AND request_count > 0
               ORDER BY request_count DESC 
               LIMIT 5""",
            (current_month,),
        ) as cursor:
            top_users = [dict(row) for row in await cursor.fetchall()]

        return {
            "total_users": total,
            "vip_count": vip_count,
            "banned_count": banned_count,
            "total_requests_this_month": total_requests,
            "top_users": top_users,
            "current_month": current_month,
        }

    # ==================== Session Operations ====================

    async def get_session(self, user_id: int) -> Optional[dict]:
        """
        Get a session by user ID.

        Args:
            user_id: Telegram user ID

        Returns:
            Session dict or None if not found
        """
        async with self._db.execute(
            "SELECT * FROM sessions WHERE user_id = ?", (user_id,)
        ) as cursor:
            row = await cursor.fetchone()
            if row:
                session = dict(row)
                # Parse JSON fields
                for field in [
                    "conversation_history",
                    "todos",
                    "preview_pages",
                    "cached_translation",
                ]:
                    if session.get(field):
                        try:
                            session[field] = json.loads(session[field])
                        except json.JSONDecodeError:
                            session[field] = [] if field != "cached_translation" else {}
                    else:
                        session[field] = [] if field != "cached_translation" else {}
                return session
            return None

    async def save_session(self, user_id: int, data: dict) -> None:
        """
        Save or update a session.

        Args:
            user_id: Telegram user ID
            data: Session data dict
        """
        # Serialize JSON fields
        data = data.copy()
        for field in [
            "conversation_history",
            "todos",
            "preview_pages",
            "cached_translation",
        ]:
            if field in data and not isinstance(data[field], str):
                data[field] = json.dumps(data[field], ensure_ascii=False)

        data["user_id"] = user_id
        data["last_activity"] = datetime.utcnow().isoformat()

        # Validate column names against whitelist (prevents SQL injection)
        self._validate_columns(set(data.keys()), SESSIONS_COLUMNS, "sessions")

        # Check if session exists
        existing = await self.get_session(user_id)

        if existing:
            # Update
            set_clause = ", ".join(f"{k} = ?" for k in data.keys() if k != "user_id")
            values = [v for k, v in data.items() if k != "user_id"] + [user_id]

            await self._db.execute(
                f"UPDATE sessions SET {set_clause} WHERE user_id = ?", values
            )
        else:
            # Insert
            data["created_at"] = datetime.utcnow().isoformat()
            columns = ", ".join(data.keys())
            placeholders = ", ".join("?" * len(data))

            await self._db.execute(
                f"INSERT INTO sessions ({columns}) VALUES ({placeholders})",
                list(data.values()),
            )

        await self._db.commit()

    async def delete_session(self, user_id: int) -> bool:
        """Delete a session."""
        await self._db.execute("DELETE FROM sessions WHERE user_id = ?", (user_id,))
        await self._db.commit()
        logger.debug(f"Deleted session for user {user_id}")
        return True

    async def cleanup_expired_sessions(self, timeout_hours: int = 1) -> int:
        """
        Delete sessions that have been inactive for too long.

        Args:
            timeout_hours: Hours of inactivity before session expires

        Returns:
            Number of sessions deleted
        """
        cutoff = (datetime.utcnow() - timedelta(hours=timeout_hours)).isoformat()

        async with self._db.execute(
            "SELECT COUNT(*) as count FROM sessions WHERE last_activity < ?", (cutoff,)
        ) as cursor:
            count = (await cursor.fetchone())["count"]

        if count > 0:
            await self._db.execute(
                "DELETE FROM sessions WHERE last_activity < ?", (cutoff,)
            )
            await self._db.commit()
            logger.info(f"Cleaned up {count} expired sessions")

        return count

    async def get_active_session_count(self) -> int:
        """Get count of active sessions."""
        async with self._db.execute("SELECT COUNT(*) as count FROM sessions") as cursor:
            return (await cursor.fetchone())["count"]

    async def get_session_stats(self) -> dict:
        """Get session statistics by state."""
        async with self._db.execute(
            "SELECT state, COUNT(*) as count FROM sessions GROUP BY state"
        ) as cursor:
            rows = await cursor.fetchall()
            stats = {row["state"]: row["count"] for row in rows}

        total = sum(stats.values())
        return {
            "total": total,
            "by_state": stats,
        }

    async def get_all_session_user_ids(self) -> list[int]:
        """Get all user IDs with active sessions."""
        async with self._db.execute("SELECT user_id FROM sessions") as cursor:
            rows = await cursor.fetchall()
            return [row["user_id"] for row in rows]

    # ==================== Activity Log Operations ====================

    async def log_activity(
        self, user_id: int, username: Optional[str], action: str, details: str = ""
    ) -> None:
        """
        Log an activity entry.

        Args:
            user_id: Telegram user ID
            username: Telegram username
            action: Action type (e.g., START, FILE_UPLOAD, AI_CHAT)
            details: Additional details
        """
        await self._db.execute(
            """INSERT INTO activity_log (timestamp, user_id, username, action, details)
               VALUES (?, ?, ?, ?, ?)""",
            (
                datetime.utcnow().isoformat(),
                user_id,
                username or "unknown",
                action,
                details,
            ),
        )
        await self._db.commit()

    async def get_recent_activity(self, limit: int = 50) -> list[dict]:
        """
        Get recent activity entries.

        Args:
            limit: Maximum number of entries to return

        Returns:
            List of activity dicts, newest first
        """
        async with self._db.execute(
            """SELECT * FROM activity_log 
               ORDER BY timestamp DESC 
               LIMIT ?""",
            (limit,),
        ) as cursor:
            rows = await cursor.fetchall()
            return [dict(row) for row in rows]

    async def cleanup_old_activity(self, days: int = 30) -> int:
        """
        Delete activity entries older than specified days.

        Args:
            days: Number of days to keep

        Returns:
            Number of entries deleted
        """
        cutoff = (datetime.utcnow() - timedelta(days=days)).isoformat()

        async with self._db.execute(
            "SELECT COUNT(*) as count FROM activity_log WHERE timestamp < ?", (cutoff,)
        ) as cursor:
            count = (await cursor.fetchone())["count"]

        if count > 0:
            await self._db.execute(
                "DELETE FROM activity_log WHERE timestamp < ?", (cutoff,)
            )
            await self._db.commit()
            logger.info(f"Cleaned up {count} old activity entries")

        return count

    async def get_activity_count(self) -> int:
        """Get total activity log entry count."""
        async with self._db.execute(
            "SELECT COUNT(*) as count FROM activity_log"
        ) as cursor:
            return (await cursor.fetchone())["count"]

    # ==================== Health & Utility ====================

    async def get_db_size(self) -> str:
        """Get database file size as human-readable string."""
        if self._db_path and self._db_path.exists():
            size = self._db_path.stat().st_size
            for unit in ["B", "KB", "MB", "GB"]:
                if size < 1024:
                    return f"{size:.1f} {unit}"
                size /= 1024
            return f"{size:.1f} TB"
        return "Unknown"

    async def get_health_info(self) -> dict:
        """Get database health information."""
        return {
            "db_size": await self.get_db_size(),
            "user_count": len(await self.get_all_users()),
            "session_count": await self.get_active_session_count(),
            "activity_count": await self.get_activity_count(),
        }

    async def vacuum(self) -> None:
        """Optimize database by running VACUUM."""
        await self._db.execute("VACUUM")
        logger.info("Database vacuumed")


# Convenience function to get database instance
def get_db() -> Database:
    """Get the database singleton instance."""
    return Database.get_instance()
