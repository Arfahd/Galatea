"""
Configuration management for Galatea Telegram Bot (Cloud Version).

Loads settings from environment variables and provides defaults.
No fcntl dependency - compatible with all platforms.
"""

import os
from pathlib import Path
from dotenv import load_dotenv

# Load environment variables from .env file
load_dotenv()


class Config:
    """Application configuration."""

    # API Keys
    TELEGRAM_BOT_TOKEN: str = os.getenv("TELEGRAM_BOT_TOKEN", "")
    ANTHROPIC_API_KEY: str = os.getenv("ANTHROPIC_API_KEY", "")

    # Admin users (can manage VIPs and ban users, automatically VIP)
    ADMIN_USERS: list[int] = [
        int(uid.strip())
        for uid in os.getenv("ADMIN_USERS", "").split(",")
        if uid.strip().isdigit()
    ]

    # VIP users from environment (unlimited requests)
    VIP_USERS: list[int] = [
        int(uid.strip())
        for uid in os.getenv("VIP_USERS", "").split(",")
        if uid.strip().isdigit()
    ]

    # Rate limiting (default 100 matches .env.example)
    MONTHLY_REQUEST_LIMIT: int = int(os.getenv("MONTHLY_REQUEST_LIMIT", "100"))

    # File handling
    MAX_FILE_SIZE_MB: int = int(os.getenv("MAX_FILE_SIZE_MB", "20"))
    MAX_FILE_SIZE_BYTES: int = MAX_FILE_SIZE_MB * 1024 * 1024

    # Paths
    BASE_DIR: Path = Path(__file__).parent.parent
    DATA_DIR: Path = BASE_DIR / "data"
    USER_FILES_DIR: Path = DATA_DIR / "user_files"
    LOGS_DIR: Path = BASE_DIR / "logs"

    # Database
    DATABASE_PATH: Path = DATA_DIR / "galatea.db"

    # Activity log retention
    ACTIVITY_RETENTION_DAYS: int = int(os.getenv("ACTIVITY_RETENTION_DAYS", "30"))

    # Claude settings
    CLAUDE_MODEL: str = "claude-sonnet-4-20250514"
    CLAUDE_MODEL_HAIKU: str = "claude-3-5-haiku-20241022"
    CLAUDE_MAX_TOKENS: int = 4096

    # Supported file types
    SUPPORTED_EXTENSIONS: set[str] = {".pdf", ".docx", ".doc", ".txt", ".xlsx", ".pptx"}

    # Document type mapping
    EXTENSION_TO_TYPE: dict[str, str] = {
        ".pdf": "pdf",
        ".docx": "docx",
        ".doc": "docx",
        ".txt": "txt",
        ".xlsx": "xlsx",
        ".pptx": "pptx",
    }

    # Session settings
    SESSION_TIMEOUT_HOURS: int = 1  # 1 hour timeout
    CLEANUP_INTERVAL_MINUTES: int = 60  # Run cleanup every 60 minutes

    # Language settings
    SUPPORTED_LANGUAGES: list[str] = ["en", "id"]
    DEFAULT_LANGUAGE: str = "en"

    # Preview settings
    PREVIEW_PAGE_SIZE: int = 1000  # Characters per preview page

    # Todo settings
    MAX_TODOS: int = 5  # Maximum todos per analysis

    # OCR Settings (for scanned PDF support)
    OCR_ENABLED: bool = os.getenv("OCR_ENABLED", "true").lower() == "true"
    OCR_LANGUAGES: str = os.getenv(
        "OCR_LANGUAGES", "eng+ind"
    )  # Tesseract language codes
    OCR_MIN_TEXT_THRESHOLD: int = int(
        os.getenv("OCR_MIN_TEXT_THRESHOLD", "100")
    )  # Minimum text chars before trying OCR

    @classmethod
    def validate(cls) -> list[str]:
        """Validate required configuration."""
        errors = []

        if not cls.TELEGRAM_BOT_TOKEN:
            errors.append("TELEGRAM_BOT_TOKEN is required")

        if not cls.ANTHROPIC_API_KEY:
            errors.append("ANTHROPIC_API_KEY is required")

        return errors

    @classmethod
    def ensure_directories(cls) -> None:
        """Create necessary directories if they don't exist."""
        cls.DATA_DIR.mkdir(parents=True, exist_ok=True)
        cls.USER_FILES_DIR.mkdir(parents=True, exist_ok=True)
        # Note: LOGS_DIR not needed for cloud (uses journald)

    @classmethod
    def get_file_type(cls, filename: str) -> str | None:
        """Get file type from filename."""
        ext = Path(filename).suffix.lower()
        return cls.EXTENSION_TO_TYPE.get(ext)


# Create singleton instance
config = Config()
