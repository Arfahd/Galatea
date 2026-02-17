"""
User-aware logging utilities.

Provides LoggerAdapter for consistent user context in log messages.
Format: [User {user_id} (@{username})] {message}
"""

import logging
from typing import Optional


class UserLoggerAdapter(logging.LoggerAdapter):
    """
    Logger adapter that prepends user context to all log messages.

    Output format: [User {user_id} (@{username})] {message}

    Example:
        >>> user_logger = UserLoggerAdapter(logger, {'user_id': 123, 'username': 'john'})
        >>> user_logger.info("Session created")
        [User 123 (@john)] Session created
    """

    def process(self, msg, kwargs):
        user_id = self.extra.get("user_id", "?")
        username = self.extra.get("username")

        if username:
            user_str = f"{user_id} (@{username})"
        else:
            user_str = str(user_id)

        return f"[User {user_str}] {msg}", kwargs


def get_user_logger(
    user_id: int,
    username: Optional[str] = None,
    logger_name: Optional[str] = None,
) -> UserLoggerAdapter:
    """
    Get a logger adapter with user context.

    Args:
        user_id: Telegram user ID
        username: Telegram username (without @), can be None if user has no username
        logger_name: Logger name (defaults to root logger)

    Returns:
        UserLoggerAdapter with user context

    Example:
        >>> user_logger = get_user_logger(123456789, "johndoe")
        >>> user_logger.info("File uploaded")
        # Output: 2026-02-17 ... - INFO - [User 123456789 (@johndoe)] File uploaded

        >>> user_logger = get_user_logger(123456789)  # No username
        >>> user_logger.info("File uploaded")
        # Output: 2026-02-17 ... - INFO - [User 123456789] File uploaded
    """
    base_logger = logging.getLogger(logger_name)
    return UserLoggerAdapter(base_logger, {"user_id": user_id, "username": username})
