"""
Activity Logger for Galatea Telegram Bot (Cloud Version)

Logs user activity to SQLite database for monitoring.
Provides async functions for logging various events.
"""

import logging
from typing import Optional

from src.database import get_db

logger = logging.getLogger(__name__)


# ==================== Core Logging Function ====================


async def log(
    action: str, user_id: int, username: Optional[str] = None, details: str = ""
) -> None:
    """
    Log an activity entry to the database.

    Args:
        action: Action type (e.g., START, FILE_UPLOAD, AI_CHAT, etc.)
        user_id: Telegram user ID
        username: Telegram username (without @)
        details: Additional details
    """
    try:
        db = get_db()
        await db.log_activity(user_id, username, action, details)
    except Exception as e:
        # Don't let logging failures break the bot
        logger.error(f"Failed to log activity: {e}")


# ==================== Convenience Functions ====================


async def log_start(user_id: int, username: Optional[str] = None) -> None:
    """Log when user starts a new session with /start."""
    await log("START", user_id, username, "New session")


async def log_file_upload(
    user_id: int, username: Optional[str], filename: str, size_str: str
) -> None:
    """Log when user uploads a file."""
    await log("FILE_UPLOAD", user_id, username, f"{filename} ({size_str})")


async def log_ai_chat(user_id: int, username: Optional[str], message: str) -> None:
    """Log when user sends a chat message to AI."""
    # Log only message length for privacy - no content
    await log("AI_CHAT", user_id, username, f"len={len(message)}")


async def log_ai_analyze(user_id: int, username: Optional[str]) -> None:
    """Log when user requests document analysis."""
    await log("AI_ANALYZE", user_id, username, "Document analysis")


async def log_complete(user_id: int, username: Optional[str]) -> None:
    """Log when AI processing completes."""
    await log("COMPLETE", user_id, username, "")


async def log_file_sent(user_id: int, username: Optional[str], filename: str) -> None:
    """Log when bot sends a file to user."""
    await log("FILE_SENT", user_id, username, filename)


async def log_error(user_id: int, username: Optional[str], error_type: str) -> None:
    """Log when an error occurs."""
    await log("ERROR", user_id, username, error_type)


async def log_rate_limited(
    user_id: int, username: Optional[str], used: int, limit: int
) -> None:
    """Log when user hits rate limit."""
    await log("RATE_LIMITED", user_id, username, f"{used}/{limit} monthly")


async def log_vip_added(
    target_user_id: int, admin_username: Optional[str] = None
) -> None:
    """Log when admin adds a VIP user."""
    admin = f"By @{admin_username}" if admin_username else "By admin"
    await log("VIP_ADDED", target_user_id, None, admin)


async def log_vip_removed(
    target_user_id: int, admin_username: Optional[str] = None
) -> None:
    """Log when admin removes a VIP user."""
    admin = f"By @{admin_username}" if admin_username else "By admin"
    await log("VIP_REMOVED", target_user_id, None, admin)


async def log_banned(target_user_id: int, admin_username: Optional[str] = None) -> None:
    """Log when admin bans a user."""
    admin = f"By @{admin_username}" if admin_username else "By admin"
    await log("BANNED", target_user_id, None, admin)


async def log_unbanned(
    target_user_id: int, admin_username: Optional[str] = None
) -> None:
    """Log when admin unbans a user."""
    admin = f"By @{admin_username}" if admin_username else "By admin"
    await log("UNBANNED", target_user_id, None, admin)


async def log_session_end(user_id: int, username: Optional[str] = None) -> None:
    """Log when user's session ends (done/cleared)."""
    await log("SESSION_END", user_id, username, "Session completed")


# ==================== Query Functions ====================


async def get_recent(count: int = 50) -> list[dict]:
    """
    Get recent activity entries.

    Args:
        count: Maximum number of entries to return

    Returns:
        List of activity dicts, newest first
    """
    try:
        db = get_db()
        return await db.get_recent_activity(count)
    except Exception as e:
        logger.error(f"Failed to get recent activity: {e}")
        return []


async def get_count() -> int:
    """Get total activity entry count."""
    try:
        db = get_db()
        return await db.get_activity_count()
    except Exception as e:
        logger.error(f"Failed to get activity count: {e}")
        return 0


async def cleanup_old(days: int = 30) -> int:
    """
    Delete activity entries older than specified days.

    Args:
        days: Number of days to keep

    Returns:
        Number of entries deleted
    """
    try:
        db = get_db()
        return await db.cleanup_old_activity(days)
    except Exception as e:
        logger.error(f"Failed to cleanup old activity: {e}")
        return 0
