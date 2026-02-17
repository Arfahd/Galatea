"""
Global rate limiter for non-AI operations.
Prevents spam/abuse of bot commands and callbacks.

This is separate from the monthly AI request quota - it's for
preventing rapid-fire button clicks and command spam.
"""

import time
from collections import defaultdict
from typing import Optional
import logging

logger = logging.getLogger(__name__)

# Configuration
MAX_REQUESTS_PER_MINUTE = 30  # Max requests in a 60-second window
MAX_REQUESTS_PER_SECOND = 3  # Burst protection


class GlobalRateLimiter:
    """
    Simple in-memory rate limiter for all bot operations.

    Uses a sliding window approach to track requests per user.
    This protects against:
    - Rapid button clicking/spam
    - Automated abuse
    - DoS attempts via excessive requests
    """

    _instance: Optional["GlobalRateLimiter"] = None

    def __new__(cls):
        if cls._instance is None:
            cls._instance = super().__new__(cls)
        return cls._instance

    def __init__(self):
        if hasattr(self, "_initialized"):
            return
        self._initialized = True
        self._requests: dict[int, list[float]] = defaultdict(list)

    def check_rate_limit(self, user_id: int) -> bool:
        """
        Check if user is within rate limits.

        Args:
            user_id: Telegram user ID

        Returns:
            True if request is allowed, False if rate limited
        """
        now = time.time()

        # Clean old entries (older than 60 seconds)
        self._requests[user_id] = [t for t in self._requests[user_id] if now - t < 60]

        requests = self._requests[user_id]

        # Check per-minute limit
        if len(requests) >= MAX_REQUESTS_PER_MINUTE:
            logger.warning(
                f"User {user_id} hit per-minute rate limit "
                f"({len(requests)}/{MAX_REQUESTS_PER_MINUTE})"
            )
            return False

        # Check per-second limit (burst protection)
        recent = [t for t in requests if now - t < 1]
        if len(recent) >= MAX_REQUESTS_PER_SECOND:
            logger.debug(f"User {user_id} hit burst rate limit")
            return False

        # Record this request
        self._requests[user_id].append(now)
        return True

    def get_user_request_count(self, user_id: int) -> int:
        """Get current request count for a user in the last minute."""
        now = time.time()
        return len([t for t in self._requests.get(user_id, []) if now - t < 60])

    def cleanup(self) -> int:
        """
        Remove stale entries from memory.

        Call this periodically (e.g., every 5 minutes) to prevent
        memory growth from inactive users.

        Returns:
            Number of user entries removed
        """
        now = time.time()
        removed = 0

        # Find users with no recent activity (5+ minutes)
        stale_users = [
            uid
            for uid, times in self._requests.items()
            if not times or now - max(times) > 300
        ]

        for uid in stale_users:
            del self._requests[uid]
            removed += 1

        if removed > 0:
            logger.debug(f"Cleaned up {removed} stale rate limit entries")

        return removed

    def get_stats(self) -> dict:
        """Get rate limiter statistics."""
        now = time.time()
        active_users = sum(
            1 for times in self._requests.values() if times and now - max(times) < 60
        )
        return {
            "tracked_users": len(self._requests),
            "active_users": active_users,
            "max_per_minute": MAX_REQUESTS_PER_MINUTE,
            "max_per_second": MAX_REQUESTS_PER_SECOND,
        }


# Singleton instance
global_rate_limiter = GlobalRateLimiter()
