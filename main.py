#!/usr/bin/env python3
"""
Galatea - File Assistant Telegram Bot (Cloud Version)

A Telegram bot that helps users read, write, and edit documents
using Claude AI for intelligent processing.

Cloud-optimized version:
- SQLite database for persistence
- No file locks (use systemd for single instance)
- Structured logging for journald
- Async-first design
"""

import logging
import sys
import signal
import asyncio
from datetime import datetime

from telegram.ext import Application
from telegram.request import HTTPXRequest

from src.config import config
from src.database import Database
from src.handlers import setup_handlers
from src.utils.session_manager import session_manager
from src.services.file_service import FileService

# Track startup time for uptime calculation
_start_time: datetime = None


def setup_logging() -> None:
    """
    Configure logging for cloud deployment.

    Logs to stdout only - systemd/journald captures and manages logs.
    """
    # Create formatter
    formatter = logging.Formatter(
        "%(asctime)s - %(name)s - %(levelname)s - %(message)s"
    )

    # Console/stdout handler only (journald captures this)
    console_handler = logging.StreamHandler(sys.stdout)
    console_handler.setLevel(logging.INFO)
    console_handler.setFormatter(formatter)

    # Configure root logger
    root_logger = logging.getLogger()
    root_logger.setLevel(logging.INFO)
    root_logger.addHandler(console_handler)

    # Reduce noise from third-party libraries
    logging.getLogger("httpx").setLevel(logging.WARNING)
    logging.getLogger("httpcore").setLevel(logging.WARNING)
    logging.getLogger("telegram").setLevel(logging.WARNING)
    logging.getLogger("anthropic").setLevel(logging.WARNING)
    logging.getLogger("aiosqlite").setLevel(logging.WARNING)


async def init_database() -> None:
    """Initialize the SQLite database."""
    logger = logging.getLogger(__name__)

    config.ensure_directories()

    await Database.init(config.DATABASE_PATH)
    logger.info(f"Database initialized at {config.DATABASE_PATH}")


async def periodic_cleanup(context) -> None:
    """
    Periodic task to clean up expired sessions and old activity logs.
    Runs every CLEANUP_INTERVAL_MINUTES (default: 60 minutes).
    """
    logger = logging.getLogger(__name__)

    try:
        # Clean expired sessions
        expired_count = await session_manager.cleanup_expired_sessions()

        # Clean orphaned user files (files for users with no active session)
        file_service = FileService()
        active_user_ids = set(await session_manager.get_all_user_ids())

        user_files_dir = config.USER_FILES_DIR
        if user_files_dir.exists():
            orphaned_cleaned = 0
            for user_dir in user_files_dir.iterdir():
                if user_dir.is_dir():
                    try:
                        user_id = int(user_dir.name)
                        if user_id not in active_user_ids:
                            # No active session - clean up files
                            count = await file_service.cleanup_user_directory(user_id)
                            if count > 0:
                                orphaned_cleaned += count
                                logger.info(
                                    f"Cleaned {count} orphaned files for user {user_id}"
                                )
                    except ValueError:
                        # Directory name is not a user ID - skip
                        pass

            if orphaned_cleaned > 0:
                logger.info(
                    f"Periodic cleanup: removed {orphaned_cleaned} orphaned files"
                )

        if expired_count > 0:
            logger.info(f"Periodic cleanup: removed {expired_count} expired sessions")

        # Clean old activity logs (older than ACTIVITY_RETENTION_DAYS)
        from src.database import get_db

        db = get_db()
        old_activity_count = await db.cleanup_old_activity(
            config.ACTIVITY_RETENTION_DAYS
        )
        if old_activity_count > 0:
            logger.info(
                f"Periodic cleanup: removed {old_activity_count} old activity entries"
            )

    except Exception as e:
        logger.error(f"Error in periodic cleanup: {e}")


def get_uptime() -> str:
    """Get bot uptime as human-readable string."""
    global _start_time
    if _start_time is None:
        return "Unknown"

    delta = datetime.now() - _start_time
    days = delta.days
    hours, remainder = divmod(delta.seconds, 3600)
    minutes, seconds = divmod(remainder, 60)

    parts = []
    if days > 0:
        parts.append(f"{days}d")
    if hours > 0:
        parts.append(f"{hours}h")
    if minutes > 0:
        parts.append(f"{minutes}m")
    if not parts:
        parts.append(f"{seconds}s")

    return " ".join(parts)


# Export for use in handlers
def get_start_time() -> datetime:
    """Get bot start time."""
    global _start_time
    return _start_time


async def main() -> None:
    """Main async entry point."""
    global _start_time
    _start_time = datetime.now()

    # Setup logging first
    setup_logging()
    logger = logging.getLogger(__name__)

    logger.info("Starting Galatea Bot (Cloud Version)...")

    # Validate configuration
    errors = config.validate()
    if errors:
        for error in errors:
            logger.error(f"Configuration error: {error}")
        logger.error("Please check your .env file and try again.")
        sys.exit(1)

    # Initialize database
    await init_database()
    db = Database.get_instance()

    # Log startup info
    health = await db.get_health_info()
    logger.info(f"Database health: {health}")

    # Create HTTP request with custom timeouts
    request = HTTPXRequest(
        connect_timeout=20.0,
        read_timeout=30.0,
        write_timeout=30.0,
        pool_timeout=10.0,
    )

    # Create application
    application = (
        Application.builder()
        .token(config.TELEGRAM_BOT_TOKEN)
        .request(request)
        .get_updates_request(request)
        .build()
    )

    # Setup handlers
    setup_handlers(application)

    # Setup periodic cleanup task
    job_queue = application.job_queue
    if job_queue:
        job_queue.run_repeating(
            periodic_cleanup,
            interval=config.CLEANUP_INTERVAL_MINUTES * 60,
            first=60,  # First run after 1 minute
            name="periodic_cleanup",
        )
        logger.info(
            f"Periodic cleanup scheduled every {config.CLEANUP_INTERVAL_MINUTES} minutes"
        )

    # Setup graceful shutdown with asyncio.Event
    shutdown_event = asyncio.Event()

    def signal_handler(sig):
        logger.info(f"Received signal {sig}, initiating graceful shutdown...")
        shutdown_event.set()

    # Register signal handlers
    loop = asyncio.get_running_loop()
    for sig in (signal.SIGINT, signal.SIGTERM):
        loop.add_signal_handler(sig, lambda s=sig: signal_handler(s))

    logger.info("Bot is ready! Starting polling...")

    # Run the bot
    try:
        await application.initialize()
        await application.start()
        await application.updater.start_polling(
            allowed_updates=["message", "callback_query"],
            drop_pending_updates=True,
            poll_interval=1.0,
            timeout=30,
        )

        # Wait for shutdown signal
        await shutdown_event.wait()

    finally:
        # Graceful cleanup sequence
        logger.info("Stopping bot...")

        await application.updater.stop()
        await application.stop()
        await application.shutdown()

        # Close database connection
        if db:
            await db.close()
            logger.info("Database connection closed")

        logger.info("Shutdown complete")


def run() -> None:
    """Entry point that handles the async event loop."""
    try:
        asyncio.run(main())
    except KeyboardInterrupt:
        pass  # Already handled by signal handler


if __name__ == "__main__":
    run()
