"""
Callback query handlers for inline keyboard buttons.
Handles all button interactions in the bot.

Cloud version - all database operations are async.
"""

import logging
from telegram import Update
from telegram.ext import ContextTypes

from ..services import ClaudeService, FileService
from ..services.analysis_service import AnalysisService
from ..utils.session_manager import UserState, session_manager
from ..utils.i18n import get_message
from ..utils import keyboards
from ..utils.rate_limiter import rate_limiter
from ..utils.global_rate_limiter import global_rate_limiter
from ..utils.user_logger import get_user_logger
from ..templates import PPTX_TEMPLATES, get_pptx_template_list

# Activity logger for monitoring
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


async def check_rate_limit_callback(query, lang: str) -> bool:
    """
    Check if user can make an AI request (for callback queries).

    Returns:
        True if allowed, False if rate limited (message already edited)
    """
    user_id = query.from_user.id

    if await rate_limiter.can_make_request(user_id):
        return True

    # Rate limited - log and send message
    status = await rate_limiter.get_status(user_id)
    await activity_logger.log_rate_limited(
        user_id,
        query.from_user.username,
        status["request_count"],
        status["limit"] if isinstance(status["limit"], int) else 0,
    )

    await query.edit_message_text(
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


async def handle_callback_query(
    update: Update, context: ContextTypes.DEFAULT_TYPE
) -> None:
    """Main callback query router."""
    query = update.callback_query
    await query.answer()

    user_id = update.effective_user.id

    # Silently ignore banned users
    if await rate_limiter.is_banned(user_id):
        return

    # Global rate limit check (prevents spam/abuse)
    if not global_rate_limiter.check_rate_limit(user_id):
        await query.answer("Too many requests. Please slow down.", show_alert=True)
        return

    session = await session_manager.get_session(user_id)
    lang = session.language
    data = query.data

    user_logger = get_user_logger(user_id, update.effective_user.username)
    user_logger.debug(f"Callback query: {data}")

    # Route to appropriate handler based on callback data prefix
    if data.startswith("action_"):
        await handle_action_callback(query, session, context)
    elif data.startswith("type_"):
        await handle_type_callback(query, session, context)
    elif data.startswith("template_"):
        await handle_template_callback(query, session, context)
    elif data.startswith("edit_"):
        await handle_edit_callback(query, session, context)
    elif data.startswith("todo_"):
        await handle_todo_callback(query, session, context)
    elif data.startswith("todos_"):
        await handle_todos_batch_callback(query, session, context)
    elif data.startswith("preview_"):
        await handle_preview_callback(query, session, context)
    elif data.startswith("translate_to_"):
        await handle_translate_callback(query, session, context)
    elif data.startswith("lang_"):
        await handle_language_callback(query, session, context)
    elif data.startswith("confirm_"):
        await handle_confirm_callback(query, session, context)
    elif data.startswith("done_"):
        await handle_done_callback(query, session, context)
    elif data.startswith("format_"):
        await handle_format_callback(query, session, context)


async def handle_action_callback(query, session, context) -> None:
    """Handle main action callbacks."""
    data = query.data
    lang = session.language

    if data == "action_new":
        # Show document type selection
        session.state = UserState.SELECTING_DOC_TYPE
        await query.edit_message_text(
            get_message("choose_doc_type", lang),
            reply_markup=keyboards.get_doc_type_menu(lang),
        )

    elif data == "action_upload":
        session.state = UserState.AWAITING_FILE
        await query.edit_message_text(
            get_message("upload_prompt", lang),
            reply_markup=keyboards.get_cancel_button(lang),
        )

    elif data == "action_help":
        await query.edit_message_text(
            get_message("help", lang), reply_markup=keyboards.get_back_button(lang)
        )

    elif data == "action_edit":
        if not session.has_file():
            await query.edit_message_text(
                get_message("no_file", lang), reply_markup=keyboards.get_main_menu(lang)
            )
            return

        await query.edit_message_text(
            get_message("choose_action", lang),
            reply_markup=keyboards.get_edit_menu(
                lang, session.current_file_type or "docx"
            ),
        )

    elif data == "action_analyze":
        if not session.has_file():
            await query.edit_message_text(
                get_message("no_file", lang), reply_markup=keyboards.get_main_menu(lang)
            )
            return

        # Check rate limit before AI call
        if not await check_rate_limit_callback(query, lang):
            return

        # Record the request
        await rate_limiter.record_request(query.from_user.id)

        await query.edit_message_text(get_message("analyzing", lang))

        # Run analysis
        try:
            todos = await get_analysis_service().analyze_document(
                content=session.current_file_content or "",
                file_type=session.current_file_type or "txt",
                language=lang,
                file_name=session.current_file_name,
            )

            session.clear_todos()
            session.add_todos(todos)
            session.state = UserState.VIEWING_TODOS

            if todos:
                # Format todos as full text list
                todos_text = keyboards.format_todos_list(todos, lang)
                header = get_message("analysis_complete", lang, count=len(todos))
                footer = get_message("todos_list_footer", lang)

                full_message = f"{header}\n\n{todos_text}\n\n{footer}"

                await query.edit_message_text(
                    full_message,
                    reply_markup=keyboards.get_todos_menu(lang, todos),
                    parse_mode="Markdown",
                )
            else:
                await query.edit_message_text(
                    get_message("todos_empty", lang),
                    reply_markup=keyboards.get_file_actions_menu(
                        lang, session.current_file_type
                    ),
                )
        except Exception as e:
            user_logger = get_user_logger(query.from_user.id, query.from_user.username)
            user_logger.error(f"Analysis error: {e}", exc_info=True)
            await query.edit_message_text(
                get_message("error_general", lang),
                reply_markup=keyboards.get_file_actions_menu(
                    lang, session.current_file_type
                ),
            )

    elif data == "action_todos":
        session.state = UserState.VIEWING_TODOS
        todos = session.todos

        if todos:
            # Format todos as full text list
            todos_text = keyboards.format_todos_list(todos, lang)
            header = get_message("todos_header", lang, count=len(todos))
            footer = get_message("todos_list_footer", lang)

            full_message = f"{header}\n\n{todos_text}\n\n{footer}"

            await query.edit_message_text(
                full_message,
                reply_markup=keyboards.get_todos_menu(lang, todos),
                parse_mode="Markdown",
            )
        else:
            await query.edit_message_text(
                get_message("todos_empty", lang),
                reply_markup=keyboards.get_file_actions_menu(
                    lang, session.current_file_type
                ),
            )

    elif data == "action_preview":
        if not session.current_file_content:
            await query.edit_message_text(
                get_message("preview_empty", lang),
                reply_markup=keyboards.get_main_menu(lang),
            )
            return

        session.state = UserState.PREVIEWING
        total_pages = session.set_preview_content(session.current_file_content)
        content, current, total = session.get_preview_page(1)

        header = get_message("preview_header", lang, current=current, total=total)
        preview_text = f"**{header}**\n\n```\n{content}\n```"

        await query.edit_message_text(
            preview_text,
            reply_markup=keyboards.get_preview_nav(lang, current, total),
            parse_mode="Markdown",
        )

    elif data == "action_done":
        if not session.has_file():
            await query.edit_message_text(
                get_message("no_file", lang), reply_markup=keyboards.get_main_menu(lang)
            )
            return

        session.state = UserState.CONFIRMING_DONE
        await query.edit_message_text(
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

    elif data == "action_cancel":
        session.state = UserState.IDLE if not session.has_file() else UserState.CHATTING

        if session.has_file():
            await query.edit_message_text(
                get_message("operation_cancelled", lang),
                reply_markup=keyboards.get_file_actions_menu(
                    lang, session.current_file_type
                ),
            )
        else:
            await query.edit_message_text(
                get_message("operation_cancelled", lang),
                reply_markup=keyboards.get_main_menu(lang),
            )

    elif data == "action_back":
        if session.has_file():
            session.state = UserState.CHATTING
            await query.edit_message_text(
                get_message("choose_action", lang),
                reply_markup=keyboards.get_file_actions_menu(
                    lang, session.current_file_type
                ),
            )
        else:
            session.state = UserState.IDLE
            await query.edit_message_text(
                get_message("choose_action", lang),
                reply_markup=keyboards.get_main_menu(lang),
            )


async def handle_type_callback(query, session, context) -> None:
    """Handle document type selection."""
    data = query.data
    lang = session.language

    type_map = {
        "type_docx": "docx",
        "type_pdf": "pdf",
        "type_xlsx": "xlsx",
        "type_pptx": "pptx",
    }

    doc_type = type_map.get(data)
    if not doc_type:
        return

    session.pending_doc_type = doc_type

    # For PowerPoint, show template selection
    if doc_type == "pptx":
        session.state = UserState.SELECTING_TEMPLATE
        templates = {k: v for k, v in PPTX_TEMPLATES.items()}
        await query.edit_message_text(
            get_message("choose_template", lang),
            reply_markup=keyboards.get_template_menu(lang, templates),
        )
    else:
        # For other types, go straight to description
        session.state = UserState.CHATTING
        await query.edit_message_text(
            get_message("describe_document", lang),
            reply_markup=keyboards.get_cancel_button(lang),
        )


async def handle_template_callback(query, session, context) -> None:
    """Handle template selection for PowerPoint."""
    data = query.data
    lang = session.language

    template_key = data.replace("template_", "")

    # Validate template key against known templates
    if template_key != "blank" and template_key not in PPTX_TEMPLATES:
        user_logger = get_user_logger(query.from_user.id, query.from_user.username)
        user_logger.warning(f"Invalid template key attempted: {template_key}")
        await query.answer("Invalid template")
        return

    session.pending_template = template_key
    session.state = UserState.CHATTING

    if template_key == "blank":
        await query.edit_message_text(
            get_message("describe_document", lang),
            reply_markup=keyboards.get_cancel_button(lang),
        )
    else:
        # Create from template immediately
        try:
            await query.edit_message_text(get_message("processing", lang))

            file_path = await get_file_service().write_pptx_from_template(
                template_key=template_key,
                filename="presentation",
                user_id=query.from_user.id,
                lang=lang,
            )

            # Read the content back
            content = await get_file_service().read_file(file_path)

            session.set_file_context(
                file_path=file_path,
                file_content=content,
                file_name=file_path.name,
                file_type="pptx",
            )
            session.state = UserState.CHATTING

            await query.edit_message_text(
                get_message("file_created", lang, filename=file_path.name),
                reply_markup=keyboards.get_file_actions_menu(lang, "pptx"),
            )
        except Exception as e:
            user_logger = get_user_logger(query.from_user.id, query.from_user.username)
            user_logger.error(f"Template creation error: {e}", exc_info=True)
            await query.edit_message_text(
                get_message("error_general", lang),
                reply_markup=keyboards.get_main_menu(lang),
            )


async def handle_edit_callback(query, session, context) -> None:
    """Handle edit operation callbacks."""
    data = query.data
    lang = session.language

    if not session.has_file():
        await query.edit_message_text(
            get_message("no_file", lang), reply_markup=keyboards.get_main_menu(lang)
        )
        return

    operation = data.replace("edit_", "")

    if operation == "translate":
        session.state = UserState.AWAITING_TRANSLATE_TARGET
        await query.edit_message_text(
            "Choose target language:" if lang == "en" else "Pilih bahasa tujuan:",
            reply_markup=keyboards.get_translate_target_menu(lang),
        )
        return

    # Handle "add" operation - just prompts user, no AI call yet
    if operation == "add":
        session.state = UserState.AWAITING_INSTRUCTION
        await query.edit_message_text(
            get_message("describe_changes", lang),
            reply_markup=keyboards.get_cancel_button(lang),
        )
        return

    # Check summary cache before AI call
    if operation == "summarize":
        cached_summary = session.get_cached_summary()
        if cached_summary:
            user_logger = get_user_logger(query.from_user.id, query.from_user.username)
            user_logger.info("Using cached summary")
            session.current_file_content = cached_summary
            session.update_content_hash()

            await query.edit_message_text(
                get_message("file_summarized", lang)
                + " "
                + get_message("cache_hit", lang),
                reply_markup=keyboards.get_after_action_menu(lang),
            )
            return

    # For other operations, process with AI
    # Check rate limit before AI call
    if not await check_rate_limit_callback(query, lang):
        return

    # Record the request
    await rate_limiter.record_request(query.from_user.id)

    # Log activity
    await activity_logger.log_ai_chat(
        query.from_user.id, query.from_user.username, f"Edit: {operation}"
    )

    await query.edit_message_text(get_message("processing", lang))

    try:
        operation_prompts = {
            "summarize": "Summarize this document concisely.",
            "rewrite": "Rewrite this document to improve clarity and flow.",
            "grammar": "Fix all grammar and spelling errors in this document.",
            "format": "Improve the formatting and structure of this document.",
        }

        prompt = operation_prompts.get(
            operation, f"Apply {operation} to this document."
        )

        response = await get_claude_service().edit_document(
            instruction=prompt,
            content=session.current_file_content,
            file_type=session.current_file_type or "txt",
            language=lang,
            operation=operation,  # Pass operation type for model selection
        )

        # Extract new content
        new_content = get_claude_service().extract_document_content(response)

        if new_content:
            session.current_file_content = new_content
            session.update_content_hash()

            # Log completion
            await activity_logger.log_complete(
                query.from_user.id, query.from_user.username
            )

            # Cache summary result
            if operation == "summarize":
                session.set_cached_summary(new_content)

            # Save updated file
            if session.current_file_path:
                await get_file_service().write_file(
                    content=new_content,
                    filename=session.current_file_path.stem,
                    user_id=query.from_user.id,
                    file_format=session.current_file_type or "txt",
                )

            # Use operation-specific feedback message
            operation_messages = {
                "summarize": "file_summarized",
                "rewrite": "file_rewritten",
                "grammar": "file_grammar_fixed",
                "format": "file_formatted",
            }
            message_key = operation_messages.get(operation, "file_updated")

            await query.edit_message_text(
                get_message(message_key, lang),
                reply_markup=keyboards.get_after_action_menu(lang),
            )
        else:
            # Show AI response without document markers
            await query.edit_message_text(
                response[:4000],  # Truncate if too long
                reply_markup=keyboards.get_file_actions_menu(
                    lang, session.current_file_type
                ),
            )

    except Exception as e:
        user_logger = get_user_logger(query.from_user.id, query.from_user.username)
        user_logger.error(f"Edit operation error: {e}", exc_info=True)
        await activity_logger.log_error(
            query.from_user.id, query.from_user.username, "Edit operation error"
        )
        await query.edit_message_text(
            get_message("error_general", lang),
            reply_markup=keyboards.get_file_actions_menu(
                lang, session.current_file_type
            ),
        )


async def handle_todo_callback(query, session, context) -> None:
    """Handle individual todo item callbacks (index-based)."""
    data = query.data
    lang = session.language
    todos = session.todos

    # Handle execute action: todo_exec_{index}
    if data.startswith("todo_exec_"):
        try:
            idx = int(data.replace("todo_exec_", ""))
            if idx < 0 or idx >= len(todos):
                await query.answer("Invalid todo index")
                return

            todo = todos[idx]

            if todo.executed:
                await query.answer(
                    "Already executed" if lang == "en" else "Sudah dijalankan"
                )
                return

            # Check rate limit before AI call
            if not await check_rate_limit_callback(query, lang):
                return

            # Record the request
            await rate_limiter.record_request(query.from_user.id)

            await query.edit_message_text(get_message("processing", lang))

            new_content = await get_analysis_service().execute_todo(
                todo=todo,
                current_content=session.current_file_content or "",
                file_type=session.current_file_type or "txt",
            )

            session.current_file_content = new_content
            todo.mark_executed()

            # Show updated todos list
            todos_text = keyboards.format_todos_list(todos, lang)
            header = get_message(
                "todo_executed", lang, description=todo.get_description(lang)
            )
            footer = get_message("todos_list_footer", lang)

            full_message = f"{header}\n\n{todos_text}\n\n{footer}"

            await query.edit_message_text(
                full_message,
                reply_markup=keyboards.get_todos_menu(lang, todos),
                parse_mode="Markdown",
            )
        except ValueError:
            await query.answer("Invalid index")
        except Exception as e:
            user_logger = get_user_logger(query.from_user.id, query.from_user.username)
            user_logger.error(f"Todo execution error: {e}", exc_info=True)
            await query.edit_message_text(
                get_message("error_general", lang),
                reply_markup=keyboards.get_todos_menu(lang, todos),
            )

    # Handle skip action: todo_skip_{index}
    elif data.startswith("todo_skip_"):
        try:
            idx = int(data.replace("todo_skip_", ""))
            if idx < 0 or idx >= len(todos):
                await query.answer("Invalid todo index")
                return

            todo = todos[idx]
            todo.mark_executed(result="skipped")

            # Show updated todos list
            todos_text = keyboards.format_todos_list(todos, lang)
            header = get_message(
                "todos_header", lang, count=len(session.get_pending_todos())
            )
            footer = get_message("todos_list_footer", lang)

            full_message = f"{header}\n\n{todos_text}\n\n{footer}"

            await query.edit_message_text(
                full_message,
                reply_markup=keyboards.get_todos_menu(lang, todos),
                parse_mode="Markdown",
            )
        except ValueError:
            await query.answer("Invalid index")

    # Handle view details: todo_idx_{index}
    elif data.startswith("todo_idx_"):
        try:
            idx = int(data.replace("todo_idx_", ""))
            if idx < 0 or idx >= len(todos):
                await query.answer("Invalid todo index")
                return

            todo = todos[idx]

            # Show full todo details
            detail = get_message(
                "todo_detail",
                lang,
                number=idx + 1,
                priority=todo.get_priority_label(lang),
                action_type=todo.action_type,
                target=todo.target,
                description=todo.get_description(lang),
                suggestion=todo.suggestion,
            )

            await query.edit_message_text(
                detail,
                reply_markup=keyboards.get_todo_action_menu(lang, idx),
            )
        except ValueError:
            await query.answer("Invalid index")


async def handle_todos_batch_callback(query, session, context) -> None:
    """Handle batch todo operations."""
    data = query.data
    lang = session.language
    todos = session.todos

    if data == "todos_execute_all":
        # Check rate limit before AI call (executing all todos uses AI)
        if not await check_rate_limit_callback(query, lang):
            return

        # Record the request
        await rate_limiter.record_request(query.from_user.id)

        await query.edit_message_text(get_message("processing", lang))

        try:
            new_content = await get_analysis_service().execute_all_todos(
                todos=todos,
                current_content=session.current_file_content or "",
                file_type=session.current_file_type or "txt",
            )

            session.current_file_content = new_content

            # Show completed message with strikethrough list
            todos_text = keyboards.format_todos_list(todos, lang)
            header = get_message("todos_all_executed", lang)

            full_message = f"{header}\n\n{todos_text}"

            await query.edit_message_text(
                full_message,
                reply_markup=keyboards.get_file_actions_menu(
                    lang, session.current_file_type
                ),
                parse_mode="Markdown",
            )
        except Exception as e:
            user_logger = get_user_logger(query.from_user.id, query.from_user.username)
            user_logger.error(f"Batch todo execution error: {e}", exc_info=True)
            await query.edit_message_text(
                get_message("error_general", lang),
                reply_markup=keyboards.get_todos_menu(lang, todos),
            )

    elif data == "todos_skip_all":
        session.mark_all_todos_executed()

        # Show skipped message
        todos_text = keyboards.format_todos_list(todos, lang)
        header = get_message("operation_cancelled", lang)

        full_message = f"{header}\n\n{todos_text}"

        await query.edit_message_text(
            full_message,
            reply_markup=keyboards.get_file_actions_menu(
                lang, session.current_file_type
            ),
            parse_mode="Markdown",
        )


async def handle_preview_callback(query, session, context) -> None:
    """Handle preview navigation."""
    data = query.data
    lang = session.language

    if data == "preview_current":
        # Just show current page again
        await query.answer()
        return

    if data.startswith("preview_page_"):
        try:
            page_num = int(data.replace("preview_page_", ""))
            # Validate page number is within reasonable bounds
            if page_num < 1 or page_num > 10000:
                await query.answer("Invalid page number")
                return
        except ValueError:
            await query.answer("Invalid page number")
            return
        content, current, total = session.get_preview_page(page_num)

        header = get_message("preview_header", lang, current=current, total=total)
        preview_text = f"**{header}**\n\n```\n{content}\n```"

        await query.edit_message_text(
            preview_text,
            reply_markup=keyboards.get_preview_nav(lang, current, total),
            parse_mode="Markdown",
        )


async def handle_translate_callback(query, session, context) -> None:
    """Handle translation target selection."""
    data = query.data
    lang = session.language

    target_lang = data.replace("translate_to_", "")

    # Check translation cache first
    cached_translation = session.get_cached_translation(target_lang)
    if cached_translation:
        user_logger = get_user_logger(query.from_user.id, query.from_user.username)
        user_logger.info("Using cached translation")
        session.current_file_content = cached_translation
        session.update_content_hash()

        await query.edit_message_text(
            get_message("file_translated", lang) + " " + get_message("cache_hit", lang),
            reply_markup=keyboards.get_after_action_menu(lang),
        )
        return

    # Check rate limit before AI call
    if not await check_rate_limit_callback(query, lang):
        return

    # Record the request
    await rate_limiter.record_request(query.from_user.id)

    # Log activity
    await activity_logger.log_ai_chat(
        query.from_user.id, query.from_user.username, f"Translate to {target_lang}"
    )

    await query.edit_message_text(get_message("processing", lang))

    try:
        response = await get_claude_service().translate_document(
            content=session.current_file_content or "",
            target_language=target_lang,
            file_type=session.current_file_type or "txt",
        )

        new_content = get_claude_service().extract_document_content(response)

        if new_content:
            # Cache the translation before updating content
            session.set_cached_translation(target_lang, new_content)
            session.current_file_content = new_content
            session.update_content_hash()

            # Log completion
            await activity_logger.log_complete(
                query.from_user.id, query.from_user.username
            )

            await query.edit_message_text(
                get_message("file_translated", lang),
                reply_markup=keyboards.get_after_action_menu(lang),
            )
        else:
            await query.edit_message_text(
                response[:4000],
                reply_markup=keyboards.get_file_actions_menu(
                    lang, session.current_file_type
                ),
            )
    except Exception as e:
        user_logger = get_user_logger(query.from_user.id, query.from_user.username)
        user_logger.error(f"Translation error: {e}", exc_info=True)
        await activity_logger.log_error(
            query.from_user.id, query.from_user.username, "Translation error"
        )
        await query.edit_message_text(
            get_message("error_general", lang),
            reply_markup=keyboards.get_file_actions_menu(
                lang, session.current_file_type
            ),
        )


async def handle_language_callback(query, session, context) -> None:
    """Handle language selection."""
    data = query.data
    user_id = query.from_user.id

    new_lang = data.replace("lang_", "")
    session.set_language(new_lang)

    # Persist language preference (survives session deletion)
    await rate_limiter.set_language(user_id, new_lang)

    await query.edit_message_text(
        get_message("language_changed", new_lang),
        reply_markup=keyboards.get_main_menu(new_lang),
    )


async def handle_confirm_callback(query, session, context) -> None:
    """Handle confirmation callbacks."""
    data = query.data
    lang = session.language

    if data == "confirm_yes":
        # Proceed with action (context dependent)
        pass
    elif data == "confirm_no":
        session.state = UserState.CHATTING if session.has_file() else UserState.IDLE

        await query.edit_message_text(
            get_message("operation_cancelled", lang),
            reply_markup=keyboards.get_file_actions_menu(
                lang, session.current_file_type
            )
            if session.has_file()
            else keyboards.get_main_menu(lang),
        )


async def handle_done_callback(query, session, context) -> None:
    """Handle done/export callbacks."""
    data = query.data
    lang = session.language
    user_id = query.from_user.id

    if data == "done_confirm":
        if not session.current_file_content:
            await query.edit_message_text(
                get_message("no_file", lang), reply_markup=keyboards.get_main_menu(lang)
            )
            return

        await query.edit_message_text(get_message("sending_file", lang))

        try:
            # Write final file
            file_path = await get_file_service().write_file(
                content=session.current_file_content,
                filename=session.current_file_name or "document",
                user_id=user_id,
                file_format=session.current_file_type or "txt",
            )

            # Send file (using context manager to properly close file handle)
            with open(file_path, "rb") as f:
                await context.bot.send_document(
                    chat_id=query.message.chat_id,
                    document=f,
                    filename=file_path.name,
                    caption=get_message("file_sent", lang),
                )

            # Log file sent
            await activity_logger.log_file_sent(
                user_id, query.from_user.username, file_path.name
            )

            # Cleanup - delete session completely (removes from memory and disk)
            await get_file_service().cleanup_user_directory(user_id)
            await session_manager.delete_session(user_id)

            # Log session end
            await activity_logger.log_session_end(user_id, query.from_user.username)

            await query.delete_message()

        except Exception as e:
            user_logger = get_user_logger(user_id, query.from_user.username)
            user_logger.error(f"File send error: {e}", exc_info=True)
            await activity_logger.log_error(
                user_id, query.from_user.username, "File send error"
            )
            await query.edit_message_text(
                get_message("error_general", lang),
                reply_markup=keyboards.get_main_menu(lang),
            )


async def handle_format_callback(query, session, context) -> None:
    """Handle format selection (legacy support)."""
    data = query.data
    lang = session.language

    format_map = {
        "format_txt": "txt",
        "format_docx": "docx",
        "format_pdf": "pdf",
        "format_xlsx": "xlsx",
        "format_pptx": "pptx",
        "format_cancel": None,
    }

    file_format = format_map.get(data)

    if file_format is None:
        session.state = UserState.IDLE
        session.pending_content = None
        await query.edit_message_text(get_message("operation_cancelled", lang))
        return

    if not session.pending_content:
        await query.edit_message_text(
            "No content to save.", reply_markup=keyboards.get_main_menu(lang)
        )
        return

    # Ask for filename
    session.state = UserState.AWAITING_FILENAME
    context.user_data["pending_format"] = file_format

    await query.edit_message_text(
        get_message("enter_filename", lang),
        reply_markup=keyboards.get_cancel_button(lang),
    )
