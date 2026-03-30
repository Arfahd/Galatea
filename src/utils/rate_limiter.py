"""
Rate limiting module for controlling API usage.
Implements VIP (unlimited) and non-VIP (monthly limit) tiers.

Uses SQLite database for persistence via the database module.
"""

import asyncio
import logging
from datetime import datetime
from typing import Optional

from ..config import config
from ..database import get_db

logger = logging.getLogger(__name__)


class RateLimiter:
    """
    Rate limiter with VIP and non-VIP tiers, plus ban management.

    - Admin users: Unlimited requests (automatically VIP), can manage VIPs and bans
    - VIP users: Unlimited requests
    - Non-VIP users: Limited requests per calendar month
    - Banned users: Cannot use bot at all

    VIP users can be added via:
    1. ADMIN_USERS environment variable (automatically VIP)
    2. VIP_USERS environment variable
    3. Admin commands (/addvip, /removevip) - stored in database
    """

    _instance: Optional["RateLimiter"] = None

    def __new__(cls):
        if cls._instance is None:
            cls._instance = super().__new__(cls)
        return cls._instance

    def __init__(self):
        # Only initialize once
        if hasattr(self, "_initialized"):
            return
        self._initialized = True
        # Cache for sync operations (updated on async calls)
        self._user_cache: dict[int, dict] = {}

    def _get_current_month(self) -> str:
        """Get current month string in YYYY-MM format."""
        return datetime.utcnow().strftime("%Y-%m")

    # ==================== Sync Methods (for non-async contexts) ====================

    def is_admin(self, user_id: int) -> bool:
        """Check if user is an admin (sync, from config only)."""
        return user_id in config.ADMIN_USERS

    def is_vip_sync(self, user_id: int) -> bool:
        """
        Check if user is VIP (sync version using cache).

        Note: This may be slightly stale. Use async is_vip() for accurate results.
        """
        # Check config first (always accurate)
        if user_id in config.VIP_USERS or user_id in config.ADMIN_USERS:
            return True

        # Check cache for database VIPs
        if user_id in self._user_cache:
            return bool(self._user_cache[user_id].get("is_vip", 0))

        return False

    def is_banned_sync(self, user_id: int) -> bool:
        """
        Check if user is banned (sync version using cache).

        Note: This may be slightly stale. Use async is_banned() for accurate results.
        """
        if user_id in self._user_cache:
            return bool(self._user_cache[user_id].get("is_banned", 0))
        return False

    # ==================== Async Methods ====================

    async def _get_user(self, user_id: int) -> dict:
        """Get or create user record."""
        db = get_db()
        user = await db.get_user(user_id)

        current_month = self._get_current_month()

        if user is None:
            # Create new user
            user = await db.upsert_user(
                user_id,
                request_count=0,
                request_month=current_month,
            )
        elif user.get("request_month") != current_month:
            # Reset for new month
            user = await db.upsert_user(
                user_id,
                request_count=0,
                request_month=current_month,
                first_request_at=None,
                last_request_at=None,
            )
            logger.info(f"Reset usage for user {user_id} (new month)")

        # Update cache
        self._user_cache[user_id] = user
        return user

    async def is_vip(self, user_id: int) -> bool:
        """Check if user is VIP (async, accurate)."""
        # Check config first
        if user_id in config.VIP_USERS or user_id in config.ADMIN_USERS:
            return True

        # Check database
        user = await self._get_user(user_id)
        return bool(user.get("is_vip", 0))

    async def is_banned(self, user_id: int) -> bool:
        """Check if user is banned (async, accurate)."""
        user = await self._get_user(user_id)
        return bool(user.get("is_banned", 0))

    async def can_make_request(self, user_id: int) -> bool:
        """Check if user can make a request."""
        # Check if banned first
        if await self.is_banned(user_id):
            return False

        # VIP users have unlimited requests
        if await self.is_vip(user_id):
            return True

        # Check request count for non-VIP
        user = await self._get_user(user_id)
        remaining = config.MONTHLY_REQUEST_LIMIT - user.get("request_count", 0)
        return remaining > 0

    async def record_request(self, user_id: int) -> bool:
        """
        Record a request for a user.

        Returns:
            True if request was recorded, False if rate limited
        """
        if not await self.can_make_request(user_id):
            return False

        user = await self._get_user(user_id)
        now = datetime.utcnow().isoformat()

        update_data = {
            "request_count": user.get("request_count", 0) + 1,
            "last_request_at": now,
        }

        if user.get("first_request_at") is None:
            update_data["first_request_at"] = now

        db = get_db()
        await db.upsert_user(user_id, **update_data)

        # Update cache
        user.update(update_data)
        self._user_cache[user_id] = user

        is_vip = await self.is_vip(user_id)
        logger.info(
            f"User {user_id} made request {update_data['request_count']}/"
            f"{config.MONTHLY_REQUEST_LIMIT} (VIP: {is_vip})"
        )

        return True

    async def get_remaining_requests(self, user_id: int) -> int:
        """Get remaining requests for a user this month."""
        if await self.is_vip(user_id):
            return -1  # Unlimited

        user = await self._get_user(user_id)
        remaining = config.MONTHLY_REQUEST_LIMIT - user.get("request_count", 0)
        return max(0, remaining)

    async def get_usage_count(self, user_id: int) -> int:
        """Get current usage count for a user."""
        user = await self._get_user(user_id)
        return user.get("request_count", 0)

    def get_reset_date(self) -> str:
        """Get the next reset date (1st of next month)."""
        now = datetime.utcnow()

        if now.month == 12:
            next_month = datetime(now.year + 1, 1, 1)
        else:
            next_month = datetime(now.year, now.month + 1, 1)

        return next_month.strftime("%Y-%m-%d")

    async def get_status(self, user_id: int) -> dict:
        """Get full status for a user."""
        user = await self._get_user(user_id)
        is_vip = await self.is_vip(user_id)

        return {
            "user_id": user_id,
            "is_vip": is_vip,
            "is_admin": self.is_admin(user_id),
            "is_banned": bool(user.get("is_banned", 0)),
            "request_count": user.get("request_count", 0),
            "limit": "unlimited" if is_vip else config.MONTHLY_REQUEST_LIMIT,
            "remaining": "unlimited"
            if is_vip
            else await self.get_remaining_requests(user_id),
            "month": user.get("request_month", self._get_current_month()),
            "reset_date": self.get_reset_date(),
            "first_request": user.get("first_request_at"),
            "last_request": user.get("last_request_at"),
        }

    # ==================== VIP Management ====================

    async def add_vip(self, user_id: int) -> bool:
        """Add a user to VIP list (database)."""
        # Can't add if already VIP from config
        if user_id in config.VIP_USERS or user_id in config.ADMIN_USERS:
            return False

        user = await self._get_user(user_id)
        if user.get("is_vip"):
            return False  # Already VIP

        db = get_db()
        await db.upsert_user(user_id, is_vip=1)

        # Update cache
        self._user_cache[user_id]["is_vip"] = 1

        logger.info(f"Added user {user_id} to VIP list")
        return True

    async def remove_vip(self, user_id: int) -> bool:
        """Remove a user from VIP list (database only, can't remove config VIPs)."""
        # Can't remove config VIPs
        if user_id in config.VIP_USERS or user_id in config.ADMIN_USERS:
            return False

        user = await self._get_user(user_id)
        if not user.get("is_vip"):
            return False  # Not a database VIP

        db = get_db()
        await db.upsert_user(user_id, is_vip=0)

        # Update cache
        self._user_cache[user_id]["is_vip"] = 0

        logger.info(f"Removed user {user_id} from VIP list")
        return True

    async def get_all_vips(self) -> dict:
        """Get all VIP users categorized by source."""
        db = get_db()
        all_users = await db.get_all_users()

        # Database VIPs (excluding those in config)
        db_vips = [
            u["user_id"]
            for u in all_users
            if u.get("is_vip") and u["user_id"] not in config.VIP_USERS
        ]

        return {
            "env_vips": list(config.VIP_USERS),
            "admin_vips": list(config.ADMIN_USERS),
            "runtime_vips": db_vips,
            "total": len(
                set(config.VIP_USERS) | set(config.ADMIN_USERS) | set(db_vips)
            ),
        }

    # ==================== Ban Management ====================

    async def ban_user(self, user_id: int) -> bool:
        """
        Ban a user.

        Returns:
            True if user was banned, False if already banned or is admin
        """
        # Cannot ban admins
        if self.is_admin(user_id):
            return False

        user = await self._get_user(user_id)
        if user.get("is_banned"):
            return False  # Already banned

        db = get_db()
        await db.upsert_user(
            user_id,
            is_banned=1,
            banned_at=datetime.utcnow().isoformat(),
            is_vip=0,  # Remove VIP status
        )

        # Update cache
        self._user_cache[user_id]["is_banned"] = 1
        self._user_cache[user_id]["is_vip"] = 0

        logger.info(f"Banned user {user_id}")
        return True

    async def unban_user(self, user_id: int) -> bool:
        """
        Unban a user.

        Returns:
            True if user was unbanned, False if not banned
        """
        user = await self._get_user(user_id)
        if not user.get("is_banned"):
            return False

        db = get_db()
        await db.upsert_user(
            user_id,
            is_banned=0,
            banned_at=None,
        )

        # Update cache
        self._user_cache[user_id]["is_banned"] = 0

        logger.info(f"Unbanned user {user_id}")
        return True

    async def get_all_banned(self) -> dict:
        """Get all banned users."""
        db = get_db()
        all_users = await db.get_all_users()

        banned = {
            u["user_id"]: u.get("banned_at", "unknown")
            for u in all_users
            if u.get("is_banned")
        }

        return {
            "banned_users": banned,
            "count": len(banned),
        }

    # ==================== Language Preference ====================

    async def get_language(self, user_id: int) -> str:
        """
        Get user's persisted language preference.
        This survives session deletion.
        """
        user = await self._get_user(user_id)
        return user.get("language", config.DEFAULT_LANGUAGE)

    async def set_language(self, user_id: int, language: str) -> None:
        """
        Set user's language preference.
        This is persisted and survives session deletion.
        """
        if language not in config.SUPPORTED_LANGUAGES:
            return

        db = get_db()
        await db.upsert_user(user_id, language=language)

        # Update cache
        if user_id in self._user_cache:
            self._user_cache[user_id]["language"] = language

        logger.debug(f"Saved language preference '{language}' for user {user_id}")

    # ==================== Statistics ====================

    async def get_stats_summary(self) -> dict:
        """Get comprehensive stats for admin /stats command."""
        db = get_db()
        stats = await db.get_user_stats()

        # Add admin info to top users
        for user in stats.get("top_users", []):
            user["is_admin"] = self.is_admin(user["user_id"])

        return stats

    async def get_all_user_ids(self) -> list[int]:
        """Get all user IDs from database (for broadcast)."""
        db = get_db()
        return await db.get_all_user_ids()


# Singleton instance
rate_limiter = RateLimiter()
