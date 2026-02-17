"""
User session management for maintaining conversation context and state.
Enhanced with multi-language support, todos, pagination, and SQLite persistence.

Cloud version - uses database module for storage instead of JSON files.
"""

import hashlib
import logging
from dataclasses import dataclass, field
from datetime import datetime, timedelta
from pathlib import Path
from typing import Optional
from enum import Enum, auto

from ..config import config
from ..database import get_db
from ..models.todo_item import TodoItem

logger = logging.getLogger(__name__)


class UserState(Enum):
    """Possible user states in the conversation flow."""

    IDLE = auto()
    CHATTING = auto()  # Conversational mode - user is chatting naturally
    AWAITING_FILE = auto()
    AWAITING_INSTRUCTION = auto()
    AWAITING_FILENAME = auto()
    AWAITING_FORMAT = auto()
    PROCESSING = auto()
    SELECTING_DOC_TYPE = auto()  # Selecting document type to create
    SELECTING_TEMPLATE = auto()  # Selecting template (for PPTX)
    VIEWING_TODOS = auto()  # Viewing todo list
    SELECTING_TODO = auto()  # Selecting a specific todo
    PREVIEWING = auto()  # Viewing paginated preview
    EDITING_CELL = auto()  # Excel: editing specific cell
    EDITING_SLIDE = auto()  # PPTX: editing specific slide
    CONFIRMING_DONE = auto()  # Confirming session completion
    AWAITING_TRANSLATE_TARGET = auto()  # Waiting for translation target language


@dataclass
class UserSession:
    """Represents a user's session data."""

    user_id: int
    state: UserState = UserState.IDLE
    language: str = "en"  # User's preferred language

    # File context
    current_file_path: Optional[Path] = None
    current_file_content: Optional[str] = None
    current_file_name: Optional[str] = None
    current_file_type: Optional[str] = None  # "docx", "pdf", "xlsx", "pptx", "txt"
    pending_content: Optional[str] = None

    # Document creation context
    pending_doc_type: Optional[str] = None  # Type being created
    pending_template: Optional[str] = None  # Template being used

    # Conversation history
    conversation_history: list = field(default_factory=list)

    # Todos/Suggestions
    todos: list = field(default_factory=list)  # List of TodoItem

    # Preview pagination
    preview_pages: list = field(default_factory=list)  # Split content pages
    preview_current_page: int = 0

    # Excel-specific
    current_sheet: Optional[str] = None
    current_cell: Optional[str] = None

    # PPTX-specific
    current_slide_index: Optional[int] = None

    # Cache fields for cost optimization
    content_hash: Optional[str] = None  # SHA-256 hash of current content
    cached_analysis_hash: Optional[str] = None  # Hash when analysis was done
    cached_translation: dict = field(default_factory=dict)  # {hash_lang: content}
    cached_summary_hash: Optional[str] = None  # Hash when summary was done
    cached_summary: Optional[str] = None  # Cached summary content

    # Session timing
    last_activity: datetime = field(default_factory=datetime.now)
    created_at: datetime = field(default_factory=datetime.now)

    # Constants
    MAX_HISTORY_LENGTH: int = 10
    SESSION_TIMEOUT_HOURS: int = config.SESSION_TIMEOUT_HOURS
    PREVIEW_PAGE_SIZE: int = config.PREVIEW_PAGE_SIZE

    def update_activity(self) -> None:
        """Update the last activity timestamp."""
        self.last_activity = datetime.now()

    def is_expired(self) -> bool:
        """Check if session has expired."""
        timeout = timedelta(hours=self.SESSION_TIMEOUT_HOURS)
        return datetime.now() - self.last_activity > timeout

    def get_time_remaining(self) -> str:
        """Get human-readable time remaining before expiration."""
        timeout = timedelta(hours=self.SESSION_TIMEOUT_HOURS)
        elapsed = datetime.now() - self.last_activity
        remaining = timeout - elapsed

        if remaining.total_seconds() <= 0:
            return "Expired"

        minutes = int(remaining.total_seconds() / 60)
        if minutes >= 60:
            hours = minutes // 60
            mins = minutes % 60
            return f"{hours}h {mins}m"
        return f"{minutes}m"

    def set_language(self, lang: str) -> None:
        """Set user's preferred language."""
        if lang in config.SUPPORTED_LANGUAGES:
            self.language = lang
            self.update_activity()

    def add_to_history(self, role: str, content: str) -> None:
        """Add a message to conversation history."""
        self.conversation_history.append({"role": role, "content": content})

        # Trim history if too long
        if len(self.conversation_history) > self.MAX_HISTORY_LENGTH * 2:
            self.conversation_history = self.conversation_history[
                -self.MAX_HISTORY_LENGTH * 2 :
            ]
        self.update_activity()

    def clear_file_context(self) -> None:
        """Clear current file context."""
        self.current_file_path = None
        self.current_file_content = None
        self.current_file_name = None
        self.current_file_type = None
        self.pending_content = None
        self.pending_doc_type = None
        self.pending_template = None
        self.current_sheet = None
        self.current_cell = None
        self.current_slide_index = None
        self.clear_preview()
        self.clear_todos()
        self.clear_cache()

    def clear_session(self) -> None:
        """Clear entire session data."""
        self.state = UserState.IDLE
        self.clear_file_context()
        self.conversation_history.clear()
        # Note: language is preserved

    def set_file_context(
        self,
        file_path: Optional[Path] = None,
        file_content: Optional[str] = None,
        file_name: Optional[str] = None,
        file_type: Optional[str] = None,
    ) -> None:
        """Set the current file context."""
        if file_path:
            self.current_file_path = file_path
        if file_content is not None:
            self.current_file_content = file_content
            self.update_content_hash()  # Update hash when content changes
        if file_name:
            self.current_file_name = file_name
        if file_type:
            self.current_file_type = file_type
        self.update_activity()

    def has_file(self) -> bool:
        """Check if session has an active file."""
        return (
            self.current_file_content is not None or self.current_file_path is not None
        )

    # Cache management
    def compute_content_hash(self) -> Optional[str]:
        """Compute hash of current document content."""
        if not self.current_file_content:
            return None
        content = self.current_file_content
        file_type = self.current_file_type or "txt"
        hash_input = f"{file_type}:{content}"
        return hashlib.sha256(hash_input.encode("utf-8")).hexdigest()[:16]

    def update_content_hash(self) -> None:
        """Update the content hash after content changes."""
        self.content_hash = self.compute_content_hash()

    def is_analysis_cache_valid(self) -> bool:
        """Check if cached analysis is still valid (content unchanged)."""
        current_hash = self.compute_content_hash()
        return current_hash and current_hash == self.cached_analysis_hash

    def is_analysis_outdated(self) -> bool:
        """Check if analysis exists but is outdated (content changed)."""
        return (
            self.cached_analysis_hash is not None
            and self.todos
            and not self.is_analysis_cache_valid()
        )

    def set_analysis_cache(self) -> None:
        """Mark current content hash as analyzed."""
        self.cached_analysis_hash = self.compute_content_hash()

    def get_cached_translation(self, target_lang: str) -> Optional[str]:
        """Get cached translation if valid."""
        current_hash = self.compute_content_hash()
        if not current_hash:
            return None
        cache_key = f"{current_hash}_{target_lang}"
        return self.cached_translation.get(cache_key)

    def set_cached_translation(self, target_lang: str, content: str) -> None:
        """Cache translation result."""
        current_hash = self.compute_content_hash()
        if current_hash:
            cache_key = f"{current_hash}_{target_lang}"
            self.cached_translation[cache_key] = content

    def get_cached_summary(self) -> Optional[str]:
        """Get cached summary if valid."""
        current_hash = self.compute_content_hash()
        if current_hash and current_hash == self.cached_summary_hash:
            return self.cached_summary
        return None

    def set_cached_summary(self, content: str) -> None:
        """Cache summary result."""
        self.cached_summary_hash = self.compute_content_hash()
        self.cached_summary = content

    def clear_cache(self) -> None:
        """Clear all cached data."""
        self.content_hash = None
        self.cached_analysis_hash = None
        self.cached_translation.clear()
        self.cached_summary_hash = None
        self.cached_summary = None

    # Todo management
    def add_todo(self, todo: TodoItem) -> None:
        """Add a todo item to the session."""
        self.todos.append(todo)
        self.update_activity()

    def add_todos(self, todos: list) -> None:
        """Add multiple todo items."""
        self.todos.extend(todos)
        self.update_activity()

    def clear_todos(self) -> None:
        """Clear all todos."""
        self.todos.clear()

    def get_todo_by_id(self, todo_id: str) -> Optional[TodoItem]:
        """Get a todo item by its ID."""
        for todo in self.todos:
            if todo.id == todo_id:
                return todo
        return None

    def get_pending_todos(self) -> list:
        """Get all unexecuted todos."""
        return [t for t in self.todos if not t.executed]

    def get_executed_todos(self) -> list:
        """Get all executed todos."""
        return [t for t in self.todos if t.executed]

    def mark_todo_executed(self, todo_id: str, result: Optional[str] = None) -> bool:
        """Mark a todo as executed."""
        todo = self.get_todo_by_id(todo_id)
        if todo:
            todo.mark_executed(result)
            self.update_activity()
            return True
        return False

    def mark_all_todos_executed(self) -> int:
        """Mark all pending todos as executed. Returns count."""
        count = 0
        for todo in self.todos:
            if not todo.executed:
                todo.mark_executed()
                count += 1
        self.update_activity()
        return count

    # Preview pagination
    def set_preview_content(self, content: str, page_size: int = None) -> int:
        """
        Set content for paginated preview.
        Returns total number of pages.
        """
        if page_size is None:
            page_size = self.PREVIEW_PAGE_SIZE

        if not content:
            self.preview_pages = []
            self.preview_current_page = 0
            return 0

        # Split content into pages
        self.preview_pages = []

        # Try to split at paragraph boundaries
        paragraphs = content.split("\n\n")
        current_page = ""

        for para in paragraphs:
            if len(current_page) + len(para) + 2 <= page_size:
                if current_page:
                    current_page += "\n\n" + para
                else:
                    current_page = para
            else:
                if current_page:
                    self.preview_pages.append(current_page)
                # Handle paragraphs longer than page_size
                if len(para) > page_size:
                    # Split long paragraph
                    for i in range(0, len(para), page_size):
                        chunk = para[i : i + page_size]
                        if i + page_size < len(para):
                            self.preview_pages.append(chunk)
                        else:
                            current_page = chunk
                else:
                    current_page = para

        if current_page:
            self.preview_pages.append(current_page)

        self.preview_current_page = 0
        self.update_activity()
        return len(self.preview_pages)

    def get_preview_page(self, page: int = None) -> tuple[str, int, int]:
        """
        Get a specific preview page.
        Returns (content, current_page (1-indexed), total_pages).
        """
        if not self.preview_pages:
            return ("", 0, 0)

        if page is not None:
            # Convert to 0-indexed
            self.preview_current_page = max(
                0, min(page - 1, len(self.preview_pages) - 1)
            )

        content = self.preview_pages[self.preview_current_page]
        return (content, self.preview_current_page + 1, len(self.preview_pages))

    def next_preview_page(self) -> tuple[str, int, int]:
        """Get next preview page."""
        if self.preview_current_page < len(self.preview_pages) - 1:
            self.preview_current_page += 1
        return self.get_preview_page()

    def previous_preview_page(self) -> tuple[str, int, int]:
        """Get previous preview page."""
        if self.preview_current_page > 0:
            self.preview_current_page -= 1
        return self.get_preview_page()

    def clear_preview(self) -> None:
        """Clear preview data."""
        self.preview_pages = []
        self.preview_current_page = 0

    def get_status_dict(self) -> dict:
        """Get session status as dictionary."""
        return {
            "filename": self.current_file_name or "None",
            "filetype": self.current_file_type or "None",
            "language": "English" if self.language == "en" else "Bahasa Indonesia",
            "time_remaining": self.get_time_remaining(),
            "pending_todos": len(self.get_pending_todos()),
        }

    def to_dict(self) -> dict:
        """Convert session to dictionary for database storage."""
        return {
            "state": self.state.name,
            "language": self.language,
            "file_path": str(self.current_file_path)
            if self.current_file_path
            else None,
            "file_content": self.current_file_content,
            "file_name": self.current_file_name,
            "file_type": self.current_file_type,
            "pending_content": self.pending_content,
            "pending_doc_type": self.pending_doc_type,
            "pending_template": self.pending_template,
            "conversation_history": self.conversation_history,
            "todos": [t.to_dict() for t in self.todos],
            "preview_pages": self.preview_pages,
            "preview_current_page": self.preview_current_page,
            "current_sheet": self.current_sheet,
            "current_cell": self.current_cell,
            "current_slide_index": self.current_slide_index,
            "content_hash": self.content_hash,
            "cached_analysis_hash": self.cached_analysis_hash,
            "cached_translation": self.cached_translation,
            "cached_summary_hash": self.cached_summary_hash,
            "cached_summary": self.cached_summary,
            "last_activity": self.last_activity.isoformat(),
            "created_at": self.created_at.isoformat(),
        }

    @classmethod
    def from_dict(cls, user_id: int, data: dict) -> "UserSession":
        """Create session from database dictionary."""
        session = cls(user_id=user_id)

        # Restore state
        try:
            session.state = UserState[data.get("state", "IDLE")]
        except KeyError:
            session.state = UserState.IDLE

        session.language = data.get("language", "en")

        # Restore file context
        file_path = data.get("file_path")
        session.current_file_path = Path(file_path) if file_path else None
        session.current_file_content = data.get("file_content")
        session.current_file_name = data.get("file_name")
        session.current_file_type = data.get("file_type")
        session.pending_content = data.get("pending_content")
        session.pending_doc_type = data.get("pending_doc_type")
        session.pending_template = data.get("pending_template")

        # Restore conversation history
        session.conversation_history = data.get("conversation_history", [])

        # Restore todos
        todos_data = data.get("todos", [])
        session.todos = [TodoItem.from_dict(t) for t in todos_data]

        # Restore preview
        session.preview_pages = data.get("preview_pages", [])
        session.preview_current_page = data.get("preview_current_page", 0)

        # Restore file-specific context
        session.current_sheet = data.get("current_sheet")
        session.current_cell = data.get("current_cell")
        session.current_slide_index = data.get("current_slide_index")

        # Restore cache fields
        session.content_hash = data.get("content_hash")
        session.cached_analysis_hash = data.get("cached_analysis_hash")
        session.cached_translation = data.get("cached_translation", {})
        session.cached_summary_hash = data.get("cached_summary_hash")
        session.cached_summary = data.get("cached_summary")

        # Restore timestamps
        try:
            session.last_activity = datetime.fromisoformat(
                data.get("last_activity", "")
            )
        except (ValueError, TypeError):
            session.last_activity = datetime.now()

        try:
            session.created_at = datetime.fromisoformat(data.get("created_at", ""))
        except (ValueError, TypeError):
            session.created_at = datetime.now()

        return session


class SessionManager:
    """
    Manages user sessions with SQLite persistence.

    This is an async-first manager. Use async methods for database operations.
    A sync cache is maintained for quick lookups in non-async contexts.
    """

    _instance: Optional["SessionManager"] = None

    def __new__(cls):
        if cls._instance is None:
            cls._instance = super().__new__(cls)
        return cls._instance

    def __init__(self):
        if hasattr(self, "_initialized"):
            return
        self._initialized = True
        self._sessions: dict[int, UserSession] = {}  # In-memory cache

    async def get_session(self, user_id: int) -> UserSession:
        """
        Get or create a session for a user.

        Loads from database if not in cache.
        """
        # Check cache first
        if user_id in self._sessions:
            session = self._sessions[user_id]

            # Check for expiration
            if session.is_expired():
                logger.info(f"Session expired for user {user_id}, creating new session")
                old_lang = session.language
                session.clear_session()
                session.language = old_lang
                await self._save_session(session)

            session.update_activity()
            return session

        # Try to load from database
        db = get_db()
        data = await db.get_session(user_id)

        if data:
            session = UserSession.from_dict(user_id, data)

            # Check for expiration
            if session.is_expired():
                logger.info(f"Loaded expired session for user {user_id}, creating new")
                old_lang = session.language
                session.clear_session()
                session.language = old_lang
        else:
            # Create new session
            session = UserSession(user_id=user_id)
            logger.info(f"Created new session for user {user_id}")

        # Cache it
        self._sessions[user_id] = session

        # Save to database
        await self._save_session(session)

        return session

    def get_session_sync(self, user_id: int) -> Optional[UserSession]:
        """
        Get session from cache only (sync, for non-async contexts).

        Returns None if session is not in cache.
        Use async get_session() for full functionality.
        """
        return self._sessions.get(user_id)

    async def _save_session(self, session: UserSession) -> None:
        """Save session to database."""
        db = get_db()
        await db.save_session(session.user_id, session.to_dict())

    async def save_session(self, user_id: int) -> None:
        """Explicitly save a session to database."""
        if user_id in self._sessions:
            await self._save_session(self._sessions[user_id])

    async def delete_session(self, user_id: int) -> None:
        """
        Completely delete a user's session from memory and database.

        Use this when a session is properly ended (done_confirm, /start).
        """
        # Remove from cache
        if user_id in self._sessions:
            del self._sessions[user_id]

        # Remove from database
        db = get_db()
        await db.delete_session(user_id)

        logger.info(f"Deleted session for user {user_id}")

    async def clear_session(self, user_id: int) -> None:
        """Clear a user's session data but keep the session."""
        if user_id in self._sessions:
            lang = self._sessions[user_id].language
            self._sessions[user_id].clear_session()
            self._sessions[user_id].language = lang
            await self._save_session(self._sessions[user_id])
            logger.info(f"Cleared session for user {user_id}")

    async def cleanup_expired_sessions(self) -> int:
        """
        Remove all expired sessions from memory and database.

        Returns count of removed sessions.
        """
        # Clean from memory cache
        expired_users = [
            user_id
            for user_id, session in self._sessions.items()
            if session.is_expired()
        ]

        for user_id in expired_users:
            del self._sessions[user_id]

        # Clean from database
        db = get_db()
        db_count = await db.cleanup_expired_sessions(config.SESSION_TIMEOUT_HOURS)

        total = max(len(expired_users), db_count)
        if total > 0:
            logger.info(f"Cleaned up {total} expired sessions")

        return total

    def get_active_session_count(self) -> int:
        """Get count of sessions in memory cache."""
        return len(self._sessions)

    async def get_session_if_exists(self, user_id: int) -> Optional[UserSession]:
        """Get session only if it exists (don't create new one)."""
        # Check cache
        if user_id in self._sessions:
            return self._sessions[user_id]

        # Check database
        db = get_db()
        data = await db.get_session(user_id)

        if data:
            session = UserSession.from_dict(user_id, data)
            self._sessions[user_id] = session
            return session

        return None

    async def get_all_user_ids(self) -> list[int]:
        """Get all user IDs with active sessions."""
        db = get_db()
        return await db.get_all_session_user_ids()

    async def get_session_stats(self) -> dict:
        """Get session statistics."""
        db = get_db()
        return await db.get_session_stats()


# Singleton instance
session_manager = SessionManager()
