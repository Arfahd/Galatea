"""Handlers package."""

from .bot_handlers import setup_handlers
from .callback_handlers import handle_callback_query

__all__ = ["setup_handlers", "handle_callback_query"]
