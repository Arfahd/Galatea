"""
Telegram bot handlers for document operations.
Cloud version with async database operations and enhanced admin commands.
"""

import logging
import psutil
from pathlib import Path
from telegram import Update
from telegram.ext import (
    Application,
    CommandHandler,
    MessageHandler,
    CallbackQueryHandler,
    ContextTypes,
    filters,
)

from ..config import config
from ..database import get_db
from ..services import ClaudeService, FileService
from ..services.claude_service import ClaudeServiceError
from ..services.file_service import FileServiceError
from ..services.analysis_service import AnalysisService
from ..utils.session_manager import UserState, session_manager
from ..utils.i18n import get_message
from ..utils import keyboards
from ..utils.rate_limiter import rate_limiter
from ..utils.user_logger import get_user_logger
from .callback_handlers import handle_callback_query

# Activity logger (async version)
import activity_logger

logger = logging.getLogger(__name__)

# Services will be initialized lazily
_claude_service = None
_file_service = None
_analysis_service = None


def get_claude_service():
    """Get or create Claude service instance."""
    global _claude_service
    if _claude_service is None:
        _claude_service = ClaudeService()
    return _claude_service


def get_file_service():
    """Get or create file service instance."""
    global _file_service
    if _file_service is None:
        _file_service = FileService()
    return _file_service


def get_analysis_service():
    """Get or create analysis service instance."""
    global _analysis_service
    if _analysis_service is None:
        _analysis_service = AnalysisService(get_claude_service())
    return _analysis_service


def is_private_chat(update: Update) -> bool:
    """Check if message is from private chat."""
    return update.effective_chat.type == "private"


async def check_rate_limit(update: Update, lang: str = "en") -> bool:
    """
    Check if user can make an AI request.

    Returns:
        True if allowed, False if rate limited (message already sent)
    """
    user_id = update.effective_user.id

    if await rate_limiter.can_make_request(user_id):
        return True

    # Rate limited - send message and log
    status = await rate_limiter.get_status(user_id)
    await activity_logger.log_rate_limited(
        user_id,
        update.effective_user.username,
        status["request_count"],
        status["limit"] if isinstance(status["limit"], int) else 0,
    )

    await update.message.reply_text(
        get_message(
            "rate_limit_reached",
            lang,
            used=status["request_count"],
            limit=status["limit"],
            reset_date=status["reset_date"],
        ),
        reply_markup=keyboards.get_main_menu(lang),
    )
    return False


async def send_not_private_message(update: Update) -> None:
    """Send message for group chat attempts."""
    await update.message.reply_text(get_message("error_not_private", "en"))


# ==================== Command Handlers ====================


async def start_command(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    """Handle /start command - initialize or reset session."""
    if not is_private_chat(update):
        await send_not_private_message(update)
        return

    user_id = update.effective_user.id

    # Silently ignore banned users
    if await rate_limiter.is_banned(user_id):
        return

    # Get persisted language preference BEFORE deleting session
    saved_lang = await rate_limiter.get_language(user_id)

    # Cleanup old files if any
    await get_file_service().cleanup_user_directory(user_id)

    # Delete old session completely
    await session_manager.delete_session(user_id)

    # Create fresh session and restore language preference
    session = await session_manager.get_session(user_id)
    session.language = saved_lang
    session.state = UserState.IDLE

    # Log activity
    await activity_logger.log_start(user_id, update.effective_user.username)

    await update.message.reply_text(
        get_message("welcome", saved_lang),
        reply_markup=keyboards.get_main_menu(saved_lang),
    )


async def help_command(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    """Handle /help command."""
    if not is_private_chat(update):
        await send_not_private_message(update)
        return

    user_id = update.effective_user.id

    # Silently ignore banned users
    if await rate_limiter.is_banned(user_id):
        return

    session = await session_manager.get_session(user_id)
    lang = session.language

    await update.message.reply_text(
        get_message("help", lang), reply_markup=keyboards.get_back_button(lang)
    )


async def new_command(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    """Handle /new command - create new document."""
    if not is_private_chat(update):
        await send_not_private_message(update)
        return

    user_id = update.effective_user.id

    # Silently ignore banned users
    if await rate_limiter.is_banned(user_id):
        return

    session = await session_manager.get_session(user_id)
    lang = session.language

    session.state = UserState.SELECTING_DOC_TYPE

    await update.message.reply_text(
        get_message("choose_doc_type", lang),
        reply_markup=keyboards.get_doc_type_menu(lang),
    )


async def edit_command(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    """Handle /edit command - show edit menu for current document."""
    if not is_private_chat(update):
        await send_not_private_message(update)
        return

    user_id = update.effective_user.id

    # Silently ignore banned users
    if await rate_limiter.is_banned(user_id):
        return

    session = await session_manager.get_session(user_id)
    lang = session.language

    if not session.has_file():
        await update.message.reply_text(
            get_message("no_file", lang), reply_markup=keyboards.get_main_menu(lang)
        )
        return

    await update.message.reply_text(
        get_message("choose_action", lang),
        reply_markup=keyboards.get_edit_menu(lang, session.current_file_type or "docx"),
    )


async def analyze_command(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    """Handle /analyze command - analyze document and generate suggestions."""
    if not is_private_chat(update):
        await send_not_private_message(update)
        return

    user_id = update.effective_user.id

    # Silently ignore banned users
    if await rate_limiter.is_banned(user_id):
        return

    session = await session_manager.get_session(user_id)
    lang = session.language

    if not session.has_file():
        await update.message.reply_text(
            get_message("no_file", lang), reply_markup=keyboards.get_main_menu(lang)
        )
        return

    # Check if we have valid cached analysis
    if session.is_analysis_cache_valid() and session.todos:
        user_logger = get_user_logger(user_id, update.effective_user.username)
        user_logger.info("Using cached analysis")
        todos = session.todos
        session.state = UserState.VIEWING_TODOS

        # Format todos as full text list
        todos_text = keyboards.format_todos_list(todos, lang)
        header = get_message("analysis_complete", lang, count=len(todos))
        cache_note = get_message("cache_hit", lang)
        footer = get_message("todos_list_footer", lang)

        full_message = f"{header} {cache_note}\n\n{todos_text}\n\n{footer}"

        await update.message.reply_text(
            full_message,
            reply_markup=keyboards.get_todos_menu(lang, todos),
            parse_mode="Markdown",
        )
        return

    # Check rate limit before AI call
    if not await check_rate_limit(update, lang):
        return

    # Record the request
    await rate_limiter.record_request(user_id)

    # Log activity
    await activity_logger.log_ai_analyze(user_id, update.effective_user.username)

    status_msg = await update.message.reply_text(get_message("analyzing", lang))

    try:
        todos = await get_analysis_service().analyze_document(
            content=session.current_file_content or "",
            file_type=session.current_file_type or "txt",
            language=lang,
            file_name=session.current_file_name,
        )

        session.clear_todos()
        session.add_todos(todos)
        session.set_analysis_cache()
        session.state = UserState.VIEWING_TODOS

        # Log completion
        await activity_logger.log_complete(user_id, update.effective_user.username)

        if todos:
            # Format todos as full text list
            todos_text = keyboards.format_todos_list(todos, lang)
            header = get_message("analysis_complete", lang, count=len(todos))
            footer = get_message("todos_list_footer", lang)

            full_message = f"{header}\n\n{todos_text}\n\n{footer}"

            await status_msg.edit_text(
                full_message,
                reply_markup=keyboards.get_todos_menu(lang, todos),
                parse_mode="Markdown",
            )
        else:
            await status_msg.edit_text(
                get_message("todos_empty", lang),
                reply_markup=keyboards.get_file_actions_menu(
                    lang, session.current_file_type
                ),
            )
    except Exception as e:
        user_logger = get_user_logger(user_id, update.effective_user.username)
        user_logger.error(f"Analysis error: {e}", exc_info=True)
        await activity_logger.log_error(
            user_id, update.effective_user.username, "Analysis error"
        )
        await status_msg.edit_text(
            get_message("error_general", lang),
            reply_markup=keyboards.get_file_actions_menu(
                lang, session.current_file_type
            ),
        )


async def todos_command(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    """Handle /todos command - show todo suggestions."""
    if not is_private_chat(update):
        await send_not_private_message(update)
        return

    user_id = update.effective_user.id

    # Silently ignore banned users
    if await rate_limiter.is_banned(user_id):
        return

    session = await session_manager.get_session(user_id)
    lang = session.language

    todos = session.todos

    if todos:
        session.state = UserState.VIEWING_TODOS

        # Format todos as full text list
        todos_text = keyboards.format_todos_list(todos, lang)
        header = get_message("todos_header", lang, count=len(todos))
        footer = get_message("todos_list_footer", lang)

        full_message = f"{header}\n\n{todos_text}\n\n{footer}"

        await update.message.reply_text(
            full_message,
            reply_markup=keyboards.get_todos_menu(lang, todos),
            parse_mode="Markdown",
        )
    else:
        await update.message.reply_text(
            get_message("todos_empty", lang),
            reply_markup=keyboards.get_file_actions_menu(
                lang, session.current_file_type
            )
            if session.has_file()
            else keyboards.get_main_menu(lang),
        )


async def preview_command(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    """Handle /preview command - show paginated document preview."""
    if not is_private_chat(update):
        await send_not_private_message(update)
        return

    user_id = update.effective_user.id

    # Silently ignore banned users
    if await rate_limiter.is_banned(user_id):
        return

    session = await session_manager.get_session(user_id)
    lang = session.language

    if not session.current_file_content:
        await update.message.reply_text(
            get_message("preview_empty", lang),
            reply_markup=keyboards.get_main_menu(lang),
        )
        return

    session.state = UserState.PREVIEWING
    total_pages = session.set_preview_content(session.current_file_content)
    content, current, total = session.get_preview_page(1)

    header = get_message("preview_header", lang, current=current, total=total)
    preview_text = f"**{header}**\n\n```\n{content}\n```"

    await update.message.reply_text(
        preview_text,
        reply_markup=keyboards.get_preview_nav(lang, current, total),
        parse_mode="Markdown",
    )


async def status_command(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    """Handle /status command - show session status."""
    if not is_private_chat(update):
        await send_not_private_message(update)
        return

    user_id = update.effective_user.id

    # Silently ignore banned users
    if await rate_limiter.is_banned(user_id):
        return

    session = await session_manager.get_session(user_id)
    lang = session.language

    status = session.get_status_dict()

    await update.message.reply_text(
        get_message("session_status", lang, **status),
        reply_markup=keyboards.get_file_actions_menu(lang, session.current_file_type)
        if session.has_file()
        else keyboards.get_main_menu(lang),
    )


async def done_command(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    """Handle /done command - finish session and send file."""
    if not is_private_chat(update):
        await send_not_private_message(update)
        return

    user_id = update.effective_user.id

    # Silently ignore banned users
    if await rate_limiter.is_banned(user_id):
        return

    session = await session_manager.get_session(user_id)
    lang = session.language

    if not session.has_file():
        await update.message.reply_text(
            get_message("no_file", lang), reply_markup=keyboards.get_main_menu(lang)
        )
        return

    session.state = UserState.CONFIRMING_DONE

    await update.message.reply_text(
        get_message(
            "confirm_done",
            lang,
            filename=session.current_file_name or "document",
            filetype=(session.current_file_type or "txt").upper(),
        ),
        reply_markup=keyboards.get_confirm_done_menu(
            lang, session.current_file_type or "txt"
        ),
    )


async def cancel_command(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    """Handle /cancel command - cancel current operation."""
    if not is_private_chat(update):
        await send_not_private_message(update)
        return

    user_id = update.effective_user.id

    # Silently ignore banned users
    if await rate_limiter.is_banned(user_id):
        return

    session = await session_manager.get_session(user_id)
    lang = session.language

    if session.state == UserState.IDLE and not session.has_file():
        await update.message.reply_text(
            get_message("nothing_to_cancel", lang),
            reply_markup=keyboards.get_main_menu(lang),
        )
        return

    session.state = UserState.CHATTING if session.has_file() else UserState.IDLE
    if not session.has_file():
        session.clear_file_context()

    await update.message.reply_text(
        get_message("operation_cancelled", lang),
        reply_markup=keyboards.get_file_actions_menu(lang, session.current_file_type)
        if session.has_file()
        else keyboards.get_main_menu(lang),
    )


async def lang_command(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    """Handle /lang command - change language."""
    if not is_private_chat(update):
        await send_not_private_message(update)
        return

    user_id = update.effective_user.id

    # Silently ignore banned users
    if await rate_limiter.is_banned(user_id):
        return

    session = await session_manager.get_session(user_id)
    lang = session.language

    await update.message.reply_text(
        get_message("choose_language", lang), reply_markup=keyboards.get_language_menu()
    )


async def files_command(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    """Handle /files command - list user's files."""
    if not is_private_chat(update):
        await send_not_private_message(update)
        return

    user_id = update.effective_user.id

    # Silently ignore banned users
    if await rate_limiter.is_banned(user_id):
        return

    session = await session_manager.get_session(user_id)
    lang = session.language

    files = get_file_service().list_user_files(user_id)

    if not files:
        await update.message.reply_text(
            get_message("files_empty", lang),
            reply_markup=keyboards.get_main_menu(lang),
        )
        return

    file_list = "\n".join([f"- {f.name}" for f in files])
    await update.message.reply_text(
        f"**{get_message('files_header', lang)}**\n{file_list}",
        parse_mode="Markdown",
    )


async def usage_command(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    """Handle /usage command - show user's rate limit status."""
    if not is_private_chat(update):
        await send_not_private_message(update)
        return

    user_id = update.effective_user.id

    # Silently ignore banned users
    if await rate_limiter.is_banned(user_id):
        return

    session = await session_manager.get_session(user_id)
    lang = session.language

    status = await rate_limiter.get_status(user_id)

    # Determine status text
    if status["is_vip"]:
        status_text = "VIP (unlimited)" if lang == "en" else "VIP (tak terbatas)"
    else:
        status_text = "Standard" if lang == "en" else "Standar"

    await update.message.reply_text(
        get_message(
            "rate_limit_status",
            lang,
            status_text=status_text,
            used=status["request_count"],
            limit=status["limit"],
            remaining=status["remaining"],
            reset_date=status["reset_date"],
        ),
        reply_markup=keyboards.get_main_menu(lang),
    )


# ==================== Admin Commands ====================


async def addvip_command(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    """Handle /addvip command - add a user to VIP list (admin only)."""
    if not is_private_chat(update):
        await send_not_private_message(update)
        return

    user_id = update.effective_user.id
    session = await session_manager.get_session(user_id)
    lang = session.language

    # Check if user is admin
    if not rate_limiter.is_admin(user_id):
        await update.message.reply_text(get_message("admin_only", lang))
        return

    # Get the target user ID from command arguments
    if not context.args or len(context.args) < 1:
        await update.message.reply_text(get_message("usage_addvip", lang))
        return

    try:
        target_user_id = int(context.args[0])
    except ValueError:
        await update.message.reply_text(get_message("invalid_user_id", lang))
        return

    # Add to VIP list
    if await rate_limiter.add_vip(target_user_id):
        await activity_logger.log_vip_added(
            target_user_id, update.effective_user.username
        )
        await update.message.reply_text(
            get_message("vip_added", lang, user_id=target_user_id)
        )
    else:
        await update.message.reply_text(
            get_message("vip_already", lang, user_id=target_user_id)
        )


async def removevip_command(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    """Handle /removevip command - remove a user from VIP list (admin only)."""
    if not is_private_chat(update):
        await send_not_private_message(update)
        return

    user_id = update.effective_user.id
    session = await session_manager.get_session(user_id)
    lang = session.language

    # Check if user is admin
    if not rate_limiter.is_admin(user_id):
        await update.message.reply_text(get_message("admin_only", lang))
        return

    # Get the target user ID from command arguments
    if not context.args or len(context.args) < 1:
        await update.message.reply_text(get_message("usage_removevip", lang))
        return

    try:
        target_user_id = int(context.args[0])
    except ValueError:
        await update.message.reply_text(get_message("invalid_user_id", lang))
        return

    # Remove from VIP list
    if await rate_limiter.remove_vip(target_user_id):
        await activity_logger.log_vip_removed(
            target_user_id, update.effective_user.username
        )
        await update.message.reply_text(
            get_message("vip_removed", lang, user_id=target_user_id)
        )
    else:
        await update.message.reply_text(
            get_message("vip_not_found", lang, user_id=target_user_id)
        )


async def viplist_command(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    """Handle /viplist command - list all VIP users (admin only)."""
    if not is_private_chat(update):
        await send_not_private_message(update)
        return

    user_id = update.effective_user.id
    session = await session_manager.get_session(user_id)
    lang = session.language

    # Check if user is admin
    if not rate_limiter.is_admin(user_id):
        await update.message.reply_text(get_message("admin_only", lang))
        return

    vips = await rate_limiter.get_all_vips()

    env_list = (
        "\n".join([f"  - {uid}" for uid in vips["env_vips"]])
        if vips["env_vips"]
        else get_message("vip_list_empty", lang)
    )
    runtime_list = (
        "\n".join([f"  - {uid}" for uid in vips["runtime_vips"]])
        if vips["runtime_vips"]
        else get_message("vip_list_empty", lang)
    )

    await update.message.reply_text(
        get_message(
            "vip_list",
            lang,
            env_count=len(vips["env_vips"]),
            env_list=env_list,
            runtime_count=len(vips["runtime_vips"]),
            runtime_list=runtime_list,
            total=vips["total"],
        )
    )


async def ban_command(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    """Handle /ban command - ban a user (admin only)."""
    if not is_private_chat(update):
        await send_not_private_message(update)
        return

    user_id = update.effective_user.id
    session = await session_manager.get_session(user_id)
    lang = session.language

    # Check if user is admin
    if not rate_limiter.is_admin(user_id):
        await update.message.reply_text(get_message("admin_only", lang))
        return

    # Get the target user ID from command arguments
    if not context.args or len(context.args) < 1:
        await update.message.reply_text(get_message("usage_ban", lang))
        return

    try:
        target_user_id = int(context.args[0])
    except ValueError:
        await update.message.reply_text(get_message("invalid_user_id", lang))
        return

    # Cannot ban admins
    if rate_limiter.is_admin(target_user_id):
        await update.message.reply_text(get_message("cannot_ban_admin", lang))
        return

    # Check if already banned
    if await rate_limiter.is_banned(target_user_id):
        await update.message.reply_text(
            get_message("ban_already", lang, user_id=target_user_id)
        )
        return

    # Send one-time ban notification to the user
    try:
        await context.bot.send_message(
            chat_id=target_user_id,
            text=get_message("user_banned", "en"),
        )
    except Exception as e:
        user_logger = get_user_logger(target_user_id, None)
        user_logger.debug(f"Could not send ban notification: {e}")

    # Ban the user
    await rate_limiter.ban_user(target_user_id)

    # Also delete their session and files
    await session_manager.delete_session(target_user_id)
    await get_file_service().cleanup_user_directory(target_user_id)

    # Log activity
    await activity_logger.log_banned(target_user_id, update.effective_user.username)

    await update.message.reply_text(
        get_message("ban_success", lang, user_id=target_user_id)
    )


async def unban_command(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    """Handle /unban command - unban a user (admin only)."""
    if not is_private_chat(update):
        await send_not_private_message(update)
        return

    user_id = update.effective_user.id
    session = await session_manager.get_session(user_id)
    lang = session.language

    # Check if user is admin
    if not rate_limiter.is_admin(user_id):
        await update.message.reply_text(get_message("admin_only", lang))
        return

    # Get the target user ID from command arguments
    if not context.args or len(context.args) < 1:
        await update.message.reply_text(get_message("usage_unban", lang))
        return

    try:
        target_user_id = int(context.args[0])
    except ValueError:
        await update.message.reply_text(get_message("invalid_user_id", lang))
        return

    # Unban the user
    if await rate_limiter.unban_user(target_user_id):
        await activity_logger.log_unbanned(
            target_user_id, update.effective_user.username
        )
        await update.message.reply_text(
            get_message("unban_success", lang, user_id=target_user_id)
        )
    else:
        await update.message.reply_text(
            get_message("unban_not_found", lang, user_id=target_user_id)
        )


async def banlist_command(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    """Handle /banlist command - list all banned users (admin only)."""
    if not is_private_chat(update):
        await send_not_private_message(update)
        return

    user_id = update.effective_user.id
    session = await session_manager.get_session(user_id)
    lang = session.language

    # Check if user is admin
    if not rate_limiter.is_admin(user_id):
        await update.message.reply_text(get_message("admin_only", lang))
        return

    banned = await rate_limiter.get_all_banned()

    if banned["count"] == 0:
        await update.message.reply_text(get_message("ban_list_empty", lang))
        return

    # Format banned users list with timestamps
    banned_list = "\n".join(
        [f"  - {uid} (banned: {ts[:10]})" for uid, ts in banned["banned_users"].items()]
    )

    await update.message.reply_text(
        get_message("ban_list", lang, count=banned["count"], list=banned_list)
    )


async def stats_command(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    """Handle /stats command - show bot usage statistics (admin only)."""
    if not is_private_chat(update):
        await send_not_private_message(update)
        return

    user_id = update.effective_user.id
    session = await session_manager.get_session(user_id)
    lang = session.language

    # Check if user is admin
    if not rate_limiter.is_admin(user_id):
        await update.message.reply_text(get_message("admin_only", lang))
        return

    stats = await rate_limiter.get_stats_summary()
    session_stats = await session_manager.get_session_stats()

    # Format top users
    if stats["top_users"]:
        top_users_list = "\n".join(
            [
                f"  {i + 1}. User {u['user_id']} - {u['request_count']} requests"
                + (" (VIP)" if u.get("is_vip") else "")
                + (" (Admin)" if u.get("is_admin") else "")
                for i, u in enumerate(stats["top_users"])
            ]
        )
    else:
        top_users_list = "  (no activity this month)"

    await update.message.reply_text(
        get_message(
            "stats_summary",
            lang,
            total_users=stats["total_users"],
            active_sessions=session_stats["total"],
            vip_count=stats["vip_count"],
            banned_count=stats["banned_count"],
            total_requests=stats["total_requests_this_month"],
            top_users=top_users_list,
        )
    )


async def broadcast_command(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    """Handle /broadcast command - send message to all users (admin only)."""
    if not is_private_chat(update):
        await send_not_private_message(update)
        return

    user_id = update.effective_user.id
    session = await session_manager.get_session(user_id)
    lang = session.language

    # Check if user is admin
    if not rate_limiter.is_admin(user_id):
        await update.message.reply_text(get_message("admin_only", lang))
        return

    # Get the message to broadcast
    if not context.args:
        # Clear any pending broadcast if no args
        context.user_data.pop("pending_broadcast", None)
        await update.message.reply_text(get_message("usage_broadcast", lang))
        return

    broadcast_message = " ".join(context.args)

    # Get all users (from database)
    all_users = await rate_limiter.get_all_user_ids()

    # Security: Require confirmation by sending same command twice
    pending = context.user_data.get("pending_broadcast")
    if pending != broadcast_message:
        # First time or different message - require confirmation
        context.user_data["pending_broadcast"] = broadcast_message
        await update.message.reply_text(
            f"Confirm broadcast to {len(all_users)} users:\n\n"
            f"---\n{broadcast_message}\n---\n\n"
            f"Send the same /broadcast command again to confirm, "
            f"or /broadcast with different text to cancel."
        )
        return

    # Confirmed - clear pending and execute
    del context.user_data["pending_broadcast"]

    # Send status message
    status_msg = await update.message.reply_text(
        f"Broadcasting to {len(all_users)} users..."
    )

    success_count = 0
    failed_count = 0

    for target_user_id in all_users:
        # Skip banned users
        if await rate_limiter.is_banned(target_user_id):
            continue

        try:
            await context.bot.send_message(
                chat_id=target_user_id,
                text=broadcast_message,
            )
            success_count += 1
        except Exception as e:
            user_logger = get_user_logger(target_user_id, None)
            user_logger.debug(f"Failed to send broadcast: {e}")
            failed_count += 1

    # Update status message
    await status_msg.edit_text(
        get_message(
            "broadcast_result", lang, success=success_count, failed=failed_count
        )
    )


# ==================== New Admin Commands (Cloud) ====================


async def activity_command(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    """Handle /activity command - show recent activity log (admin only)."""
    if not is_private_chat(update):
        await send_not_private_message(update)
        return

    user_id = update.effective_user.id
    session = await session_manager.get_session(user_id)
    lang = session.language

    # Check if user is admin
    if not rate_limiter.is_admin(user_id):
        await update.message.reply_text(get_message("admin_only", lang))
        return

    # Get count from args (default 10)
    count = 10
    if context.args:
        try:
            count = min(int(context.args[0]), 50)  # Max 50
        except ValueError:
            pass

    # Get recent activity
    activities = await activity_logger.get_recent(count)

    if not activities:
        await update.message.reply_text(get_message("activity_empty", lang))
        return

    # Format activity list
    lines = [get_message("activity_header", lang, count=len(activities))]
    lines.append("```")

    for entry in activities:
        time_str = entry.get("timestamp", "")[:19]  # Trim to seconds
        if len(time_str) > 10:
            time_str = time_str[11:]  # Just time part

        username = entry.get("username", "unknown")
        if username and username != "unknown":
            user_display = f"@{username}"[:12]
        else:
            user_display = str(entry.get("user_id", "?"))[:12]

        action = entry.get("action", "?")[:12]
        details = entry.get("details", "")[:20]

        lines.append(f"{time_str} | {user_display:12} | {action:12} | {details}")

    lines.append("```")

    await update.message.reply_text(
        "\n".join(lines),
        parse_mode="Markdown",
    )


async def sessions_command(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    """Handle /sessions command - show active sessions (admin only)."""
    if not is_private_chat(update):
        await send_not_private_message(update)
        return

    user_id = update.effective_user.id
    session = await session_manager.get_session(user_id)
    lang = session.language

    # Check if user is admin
    if not rate_limiter.is_admin(user_id):
        await update.message.reply_text(get_message("admin_only", lang))
        return

    # Get session stats
    stats = await session_manager.get_session_stats()
    by_state = stats.get("by_state", {})

    await update.message.reply_text(
        get_message(
            "sessions_summary",
            lang,
            total=stats["total"],
            idle=by_state.get("IDLE", 0),
            chatting=by_state.get("CHATTING", 0),
            processing=by_state.get("PROCESSING", 0),
            other=stats["total"]
            - by_state.get("IDLE", 0)
            - by_state.get("CHATTING", 0)
            - by_state.get("PROCESSING", 0),
        )
    )


async def health_command(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    """Handle /health command - show system health (admin only)."""
    if not is_private_chat(update):
        await send_not_private_message(update)
        return

    user_id = update.effective_user.id
    session = await session_manager.get_session(user_id)
    lang = session.language

    # Check if user is admin
    if not rate_limiter.is_admin(user_id):
        await update.message.reply_text(get_message("admin_only", lang))
        return

    # Get health info
    db = get_db()
    db_health = await db.get_health_info()

    # Get uptime
    from main import get_uptime

    uptime = get_uptime()

    # Get memory usage
    try:
        process = psutil.Process()
        memory_mb = process.memory_info().rss / 1024 / 1024
        memory_str = f"{memory_mb:.1f} MB"
    except Exception:
        memory_str = "Unknown"

    await update.message.reply_text(
        get_message(
            "health_info",
            lang,
            uptime=uptime,
            memory=memory_str,
            db_size=db_health["db_size"],
            sessions=db_health["session_count"],
            activity_count=db_health["activity_count"],
        )
    )


# ==================== Message Handlers ====================


async def handle_document(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    """Handle uploaded documents."""
    if not is_private_chat(update):
        await send_not_private_message(update)
        return

    user_id = update.effective_user.id

    # Silently ignore banned users
    if await rate_limiter.is_banned(user_id):
        return

    document = update.message.document
    filename = document.file_name or "unknown"
    extension = Path(filename).suffix.lower()

    session = await session_manager.get_session(user_id)
    lang = session.language

    # Validate file type
    if extension not in config.SUPPORTED_EXTENSIONS:
        await update.message.reply_text(
            get_message(
                "unsupported_format",
                lang,
                extension=extension,
                formats=", ".join(config.SUPPORTED_EXTENSIONS),
            )
        )
        return

    # Validate file size
    if document.file_size > config.MAX_FILE_SIZE_BYTES:
        await update.message.reply_text(
            get_message("file_too_large", lang, max_size=config.MAX_FILE_SIZE_MB)
        )
        return

    # Get file type
    file_type = config.get_file_type(filename)

    # Show processing status
    status_msg = await update.message.reply_text(
        get_message(
            "file_received", lang, filename=filename, filetype=file_type.upper()
        )
    )

    try:
        # Download file
        file = await context.bot.get_file(document.file_id)
        file_bytes = await file.download_as_bytearray()

        # Read content
        content = await get_file_service().read_file_from_bytes(
            bytes(file_bytes), filename
        )

        # Save file
        saved_path = await get_file_service().save_uploaded_file(
            bytes(file_bytes), filename, user_id
        )

        # Update session
        session.set_file_context(
            file_path=saved_path,
            file_content=content,
            file_name=filename,
            file_type=file_type,
        )
        session.state = UserState.CHATTING

        # Get file size
        file_size = get_file_service().get_file_size_str(saved_path)

        # Log activity
        await activity_logger.log_file_upload(
            user_id, update.effective_user.username, filename, file_size
        )

        # Check if there's a caption with instructions
        if update.message.caption:
            await status_msg.delete()
            await process_chat_message(update, context, update.message.caption)
        else:
            await status_msg.edit_text(
                get_message(
                    "file_loaded",
                    lang,
                    filename=filename,
                    filetype=file_type.upper(),
                    size=file_size,
                ),
                reply_markup=keyboards.get_file_actions_menu(lang, file_type),
            )

    except FileServiceError as e:
        user_logger = get_user_logger(user_id, update.effective_user.username)
        user_logger.error(f"File read error: {e}", exc_info=True)
        await activity_logger.log_error(
            user_id, update.effective_user.username, "File read error"
        )
        await status_msg.edit_text(get_message("error_general", lang))
    except Exception as e:
        user_logger = get_user_logger(user_id, update.effective_user.username)
        user_logger.error(f"Error handling document: {e}", exc_info=True)
        await activity_logger.log_error(
            user_id, update.effective_user.username, "General error"
        )
        await status_msg.edit_text(get_message("error_general", lang))


async def handle_text_message(
    update: Update, context: ContextTypes.DEFAULT_TYPE
) -> None:
    """Handle text messages - main conversational handler."""
    if not is_private_chat(update):
        return  # Silently ignore group messages

    user_id = update.effective_user.id

    # Silently ignore banned users
    if await rate_limiter.is_banned(user_id):
        return

    session = await session_manager.get_session(user_id)
    user_message = update.message.text

    # Route based on state
    if session.state == UserState.AWAITING_FILENAME:
        await handle_filename_input(update, context, user_message)
    elif session.state == UserState.AWAITING_INSTRUCTION:
        await process_instruction(update, context, user_message)
    else:
        # Default: conversational mode
        await process_chat_message(update, context, user_message)


async def handle_filename_input(
    update: Update, context: ContextTypes.DEFAULT_TYPE, filename: str
) -> None:
    """Handle filename input for saving files."""
    user_id = update.effective_user.id
    session = await session_manager.get_session(user_id)
    lang = session.language

    file_format = context.user_data.get(
        "pending_format", session.current_file_type or "txt"
    )
    content = session.pending_content or session.current_file_content

    if not content:
        await update.message.reply_text(
            "No content to save.", reply_markup=keyboards.get_main_menu(lang)
        )
        session.state = UserState.IDLE
        return

    status_msg = await update.message.reply_text(get_message("processing", lang))

    try:
        # Save the file
        file_path = await get_file_service().write_file(
            content=content,
            filename=filename,
            user_id=user_id,
            file_format=file_format,
        )

        # Send the file
        with open(file_path, "rb") as f:
            await context.bot.send_document(
                chat_id=update.effective_chat.id,
                document=f,
                filename=file_path.name,
                caption=get_message("file_sent", lang),
            )

        # Log file sent
        await activity_logger.log_file_sent(
            user_id, update.effective_user.username, file_path.name
        )

        await status_msg.delete()

        # Clean up context data
        context.user_data.pop("pending_format", None)

        # Cleanup user files and delete session completely
        await get_file_service().cleanup_user_directory(user_id)
        await session_manager.delete_session(user_id)

        # Log session end
        await activity_logger.log_session_end(user_id, update.effective_user.username)

    except Exception as e:
        user_logger = get_user_logger(user_id, update.effective_user.username)
        user_logger.error(f"Error saving file: {e}", exc_info=True)
        await activity_logger.log_error(
            user_id, update.effective_user.username, "File write error"
        )
        await status_msg.edit_text(get_message("error_general", lang))
        session.state = UserState.IDLE


async def process_instruction(
    update: Update, context: ContextTypes.DEFAULT_TYPE, instruction: str
) -> None:
    """Process a specific instruction for the current file."""
    user_id = update.effective_user.id
    session = await session_manager.get_session(user_id)
    lang = session.language

    # Check rate limit before AI call
    if not await check_rate_limit(update, lang):
        return

    # Record the request
    await rate_limiter.record_request(user_id)

    # Log activity
    await activity_logger.log_ai_chat(
        user_id, update.effective_user.username, instruction
    )

    status_msg = await update.message.reply_text(get_message("processing", lang))
    session.state = UserState.PROCESSING

    try:
        session.add_to_history("user", instruction)

        response = await get_claude_service().process_file_request(
            user_message=instruction,
            file_content=session.current_file_content,
            file_name=session.current_file_name,
            conversation_history=session.conversation_history[:-1],
        )

        session.add_to_history("assistant", response)

        # Check for document content
        document_content = get_claude_service().extract_document_content(response)

        # Log completion
        await activity_logger.log_complete(user_id, update.effective_user.username)

        if document_content:
            session.current_file_content = document_content
            session.state = UserState.CHATTING

            # Clean response for display
            display_response = (
                response.replace("[DOCUMENT_START]", "")
                .replace("[DOCUMENT_END]", "")
                .strip()
            )
            if len(display_response) > 500:
                display_response = display_response[:500] + "..."

            await status_msg.edit_text(
                get_message("file_updated", lang) + f"\n\n{display_response}",
                reply_markup=keyboards.get_after_action_menu(lang),
            )
        else:
            session.state = UserState.CHATTING
            await status_msg.edit_text(
                response[:4000] if len(response) > 4000 else response,
                reply_markup=keyboards.get_file_actions_menu(
                    lang, session.current_file_type
                ),
            )

    except ClaudeServiceError as e:
        session.state = UserState.CHATTING
        await activity_logger.log_error(
            user_id, update.effective_user.username, "Claude API error"
        )
        await status_msg.edit_text(
            get_message("error_ai", "en"),
            reply_markup=keyboards.get_file_actions_menu(
                lang, session.current_file_type
            ),
        )
    except Exception as e:
        user_logger = get_user_logger(user_id, update.effective_user.username)
        user_logger.error(f"Error processing instruction: {e}", exc_info=True)
        session.state = UserState.CHATTING
        await activity_logger.log_error(
            user_id, update.effective_user.username, "General error"
        )
        await status_msg.edit_text(get_message("error_general", lang))


async def process_chat_message(
    update: Update, context: ContextTypes.DEFAULT_TYPE, message: str
) -> None:
    """Process conversational message with AI."""
    user_id = update.effective_user.id
    session = await session_manager.get_session(user_id)
    lang = session.language

    # Check rate limit before AI call
    if not await check_rate_limit(update, lang):
        return

    # Record the request
    await rate_limiter.record_request(user_id)

    # Log activity
    await activity_logger.log_ai_chat(user_id, update.effective_user.username, message)

    status_msg = await update.message.reply_text(get_message("thinking", lang))

    try:
        session.add_to_history("user", message)

        # Use chat mode for conversational response
        response = await get_claude_service().chat(
            user_message=message,
            language=lang,
            file_content=session.current_file_content,
            file_name=session.current_file_name,
            file_type=session.current_file_type,
            conversation_history=session.conversation_history[:-1],
        )

        session.add_to_history("assistant", response)

        # Log completion
        await activity_logger.log_complete(user_id, update.effective_user.username)

        # Check if AI generated document content
        document_content = get_claude_service().extract_document_content(response)

        if document_content:
            # AI created/modified document
            if not session.has_file():
                # New document creation
                file_type = session.pending_doc_type or "docx"

                # Save the new document
                file_path = await get_file_service().write_file(
                    content=document_content,
                    filename="document",
                    user_id=user_id,
                    file_format=file_type,
                )

                session.set_file_context(
                    file_path=file_path,
                    file_content=document_content,
                    file_name=file_path.name,
                    file_type=file_type,
                )

                display_response = (
                    response.replace("[DOCUMENT_START]", "")
                    .replace("[DOCUMENT_END]", "")
                    .strip()
                )

                await status_msg.edit_text(
                    get_message("file_created", lang, filename=file_path.name)
                    + f"\n\n{display_response[:500]}{'...' if len(display_response) > 500 else ''}",
                    reply_markup=keyboards.get_file_actions_menu(lang, file_type),
                )
            else:
                # Update existing document
                session.current_file_content = document_content

                display_response = (
                    response.replace("[DOCUMENT_START]", "")
                    .replace("[DOCUMENT_END]", "")
                    .strip()
                )

                await status_msg.edit_text(
                    get_message("file_updated", lang)
                    + f"\n\n{display_response[:500]}{'...' if len(display_response) > 500 else ''}",
                    reply_markup=keyboards.get_after_action_menu(lang),
                )

            session.state = UserState.CHATTING
        else:
            # Regular chat response
            session.state = UserState.CHATTING

            # Truncate if too long
            display_text = response[:4000] if len(response) > 4000 else response

            if session.has_file():
                await status_msg.edit_text(
                    display_text,
                    reply_markup=keyboards.get_file_actions_menu(
                        lang, session.current_file_type
                    ),
                )
            else:
                await status_msg.edit_text(
                    display_text, reply_markup=keyboards.get_main_menu(lang)
                )

    except ClaudeServiceError as e:
        logger.error(f"Claude service error: {e}")
        await activity_logger.log_error(
            user_id, update.effective_user.username, "Claude API error"
        )
        await status_msg.edit_text(
            get_message("error_ai", "en"), reply_markup=keyboards.get_main_menu(lang)
        )
    except Exception as e:
        user_logger = get_user_logger(user_id, update.effective_user.username)
        user_logger.error(f"Error in chat: {e}", exc_info=True)
        await activity_logger.log_error(
            user_id, update.effective_user.username, "General error"
        )
        await status_msg.edit_text(get_message("error_general", lang))


async def error_handler(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    """Handle errors with resilience."""
    try:
        logger.error(f"Update {update} caused error {context.error}")

        # Get user's language preference if possible
        lang = "en"
        if update and update.effective_user:
            session = await session_manager.get_session_if_exists(
                update.effective_user.id
            )
            if session:
                lang = session.language

        if update and update.effective_message:
            try:
                await update.effective_message.reply_text(
                    get_message("error_general", lang)
                )
            except Exception as reply_error:
                logger.error(f"Failed to send error message to user: {reply_error}")
    except Exception as e:
        logger.error(f"Error handler itself failed: {e}")


def setup_handlers(application: Application) -> None:
    """Set up all bot handlers."""
    # Command handlers
    application.add_handler(CommandHandler("start", start_command))
    application.add_handler(CommandHandler("help", help_command))
    application.add_handler(CommandHandler("new", new_command))
    application.add_handler(CommandHandler("edit", edit_command))
    application.add_handler(CommandHandler("analyze", analyze_command))
    application.add_handler(CommandHandler("todos", todos_command))
    application.add_handler(CommandHandler("preview", preview_command))
    application.add_handler(CommandHandler("status", status_command))
    application.add_handler(CommandHandler("done", done_command))
    application.add_handler(CommandHandler("cancel", cancel_command))
    application.add_handler(CommandHandler("lang", lang_command))
    application.add_handler(CommandHandler("files", files_command))
    application.add_handler(CommandHandler("usage", usage_command))

    # Admin commands
    application.add_handler(CommandHandler("addvip", addvip_command))
    application.add_handler(CommandHandler("removevip", removevip_command))
    application.add_handler(CommandHandler("viplist", viplist_command))
    application.add_handler(CommandHandler("ban", ban_command))
    application.add_handler(CommandHandler("unban", unban_command))
    application.add_handler(CommandHandler("banlist", banlist_command))
    application.add_handler(CommandHandler("stats", stats_command))
    application.add_handler(CommandHandler("broadcast", broadcast_command))

    # New cloud admin commands
    application.add_handler(CommandHandler("activity", activity_command))
    application.add_handler(CommandHandler("sessions", sessions_command))
    application.add_handler(CommandHandler("health", health_command))

    # Legacy command support
    application.add_handler(CommandHandler("clear", cancel_command))

    # Callback query handler for all buttons
    application.add_handler(CallbackQueryHandler(handle_callback_query))

    # Document handler
    application.add_handler(MessageHandler(filters.Document.ALL, handle_document))

    # Text message handler
    application.add_handler(
        MessageHandler(filters.TEXT & ~filters.COMMAND, handle_text_message)
    )

    # Error handler
    application.add_error_handler(error_handler)
