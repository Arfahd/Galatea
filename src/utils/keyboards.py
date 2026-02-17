"""
Inline keyboard builders for Telegram bot.
All keyboards support bilingual display (English/Indonesian).
"""

from telegram import InlineKeyboardButton, InlineKeyboardMarkup
from typing import Optional
from .i18n import get_message, get_button_text


def get_main_menu(lang: str = "en") -> InlineKeyboardMarkup:
    """Get main menu keyboard."""
    return InlineKeyboardMarkup(
        [
            [
                InlineKeyboardButton(
                    get_button_text("create_new", lang), callback_data="action_new"
                )
            ],
            [
                InlineKeyboardButton(
                    get_button_text("upload", lang), callback_data="action_upload"
                )
            ],
            [
                InlineKeyboardButton(
                    get_button_text("help", lang), callback_data="action_help"
                )
            ],
        ]
    )


def get_doc_type_menu(lang: str = "en") -> InlineKeyboardMarkup:
    """Get document type selection keyboard."""
    return InlineKeyboardMarkup(
        [
            [
                InlineKeyboardButton(
                    get_button_text("word", lang), callback_data="type_docx"
                ),
                InlineKeyboardButton(
                    get_button_text("pdf", lang), callback_data="type_pdf"
                ),
            ],
            [
                InlineKeyboardButton(
                    get_button_text("excel", lang), callback_data="type_xlsx"
                ),
                InlineKeyboardButton(
                    get_button_text("powerpoint", lang), callback_data="type_pptx"
                ),
            ],
            [
                InlineKeyboardButton(
                    get_button_text("cancel", lang), callback_data="action_cancel"
                )
            ],
        ]
    )


def get_template_menu(lang: str = "en", templates: dict = None) -> InlineKeyboardMarkup:
    """Get template selection keyboard for PowerPoint."""
    buttons = []

    # Blank option always first
    buttons.append(
        [
            InlineKeyboardButton(
                get_button_text("blank", lang), callback_data="template_blank"
            )
        ]
    )

    if templates:
        for key, template in templates.items():
            if key == "blank":
                continue
            name = template.get(f"name_{lang}", template.get("name_en", key))
            buttons.append(
                [InlineKeyboardButton(name, callback_data=f"template_{key}")]
            )

    buttons.append(
        [
            InlineKeyboardButton(
                get_button_text("cancel", lang), callback_data="action_cancel"
            )
        ]
    )

    return InlineKeyboardMarkup(buttons)


def get_edit_menu(lang: str = "en", file_type: str = "docx") -> InlineKeyboardMarkup:
    """Get edit operations keyboard based on file type."""

    # Common operations for text-based documents
    common_buttons = [
        [
            InlineKeyboardButton(
                get_button_text("summarize", lang), callback_data="edit_summarize"
            ),
            InlineKeyboardButton(
                get_button_text("translate", lang), callback_data="edit_translate"
            ),
        ],
        [
            InlineKeyboardButton(
                get_button_text("rewrite", lang), callback_data="edit_rewrite"
            ),
            InlineKeyboardButton(
                get_button_text("fix_grammar", lang), callback_data="edit_grammar"
            ),
        ],
        [
            InlineKeyboardButton(
                get_button_text("add_content", lang), callback_data="edit_add"
            ),
            InlineKeyboardButton(
                get_button_text("format", lang), callback_data="edit_format"
            ),
        ],
    ]

    # File type specific buttons
    if file_type == "xlsx":
        specific_buttons = [
            [
                InlineKeyboardButton(
                    "Edit Cell" if lang == "en" else "Edit Sel",
                    callback_data="edit_cell",
                ),
                InlineKeyboardButton(
                    "Add Row" if lang == "en" else "Tambah Baris",
                    callback_data="edit_add_row",
                ),
            ],
            [
                InlineKeyboardButton(
                    "Add Column" if lang == "en" else "Tambah Kolom",
                    callback_data="edit_add_column",
                ),
            ],
        ]
        buttons = (
            specific_buttons + common_buttons[:2]
        )  # Less text operations for Excel
    elif file_type == "pptx":
        specific_buttons = [
            [
                InlineKeyboardButton(
                    "Edit Slide" if lang == "en" else "Edit Slide",
                    callback_data="edit_slide",
                ),
                InlineKeyboardButton(
                    "Add Slide" if lang == "en" else "Tambah Slide",
                    callback_data="edit_add_slide",
                ),
            ],
        ]
        buttons = specific_buttons + common_buttons
    else:
        buttons = common_buttons

    # Add back/cancel
    buttons.append(
        [
            InlineKeyboardButton(
                get_button_text("back", lang), callback_data="action_back"
            ),
            InlineKeyboardButton(
                get_button_text("cancel", lang), callback_data="action_cancel"
            ),
        ]
    )

    return InlineKeyboardMarkup(buttons)


def get_file_actions_menu(
    lang: str = "en", file_type: str = "docx"
) -> InlineKeyboardMarkup:
    """Get file action menu after file is loaded."""
    return InlineKeyboardMarkup(
        [
            [
                InlineKeyboardButton(
                    get_button_text("edit", lang), callback_data="action_edit"
                ),
                InlineKeyboardButton(
                    get_button_text("analyze", lang), callback_data="action_analyze"
                ),
            ],
            [
                InlineKeyboardButton(
                    get_button_text("preview", lang), callback_data="action_preview"
                ),
                InlineKeyboardButton(
                    get_button_text("todos", lang), callback_data="action_todos"
                ),
            ],
            [
                InlineKeyboardButton(
                    get_button_text("done", lang), callback_data="action_done"
                ),
            ],
        ]
    )


def get_todos_menu(
    lang: str = "en", todos: list = None, max_display: int = 5
) -> InlineKeyboardMarkup:
    """Get todo list keyboard with numbered buttons."""
    buttons = []

    if todos:
        # Create numbered buttons in a single row
        number_buttons = []
        for i, todo in enumerate(todos[:max_display]):
            # Show checkmark for executed todos
            if todo.executed:
                label = f"[{i + 1}]"
            else:
                label = f" {i + 1} "

            number_buttons.append(
                InlineKeyboardButton(label, callback_data=f"todo_idx_{i}")
            )

        # Add numbered buttons as single row (Telegram will wrap if needed)
        if number_buttons:
            buttons.append(number_buttons)

        # Action buttons
        pending_count = sum(1 for t in todos if not t.executed)
        if pending_count > 0:
            buttons.append(
                [
                    InlineKeyboardButton(
                        get_button_text("execute_all", lang),
                        callback_data="todos_execute_all",
                    ),
                    InlineKeyboardButton(
                        get_button_text("skip_all", lang),
                        callback_data="todos_skip_all",
                    ),
                ]
            )

    buttons.append(
        [
            InlineKeyboardButton(
                get_button_text("back", lang), callback_data="action_back"
            ),
        ]
    )

    return InlineKeyboardMarkup(buttons)


def format_todos_list(todos: list, lang: str = "en") -> str:
    """Format todos as numbered list with full descriptions for display."""
    if not todos:
        return ""

    lines = []
    for i, todo in enumerate(todos, 1):
        priority_label = todo.get_priority_label(lang)
        description = todo.get_description(lang)

        # Use strikethrough for executed todos
        if todo.executed:
            lines.append(f"~{i}. [{priority_label}] {description}~")
        else:
            lines.append(f"{i}. [{priority_label}] {description}")

    return "\n\n".join(lines)


def get_todo_action_menu(lang: str = "en", todo_idx: int = 0) -> InlineKeyboardMarkup:
    """Get action menu for a specific todo item (by index)."""
    return InlineKeyboardMarkup(
        [
            [
                InlineKeyboardButton(
                    get_button_text("execute", lang),
                    callback_data=f"todo_exec_{todo_idx}",
                ),
                InlineKeyboardButton(
                    get_button_text("skip", lang), callback_data=f"todo_skip_{todo_idx}"
                ),
            ],
            [
                InlineKeyboardButton(
                    get_button_text("back", lang), callback_data="action_todos"
                )
            ],
        ]
    )


def get_preview_nav(
    lang: str = "en", current_page: int = 1, total_pages: int = 1
) -> InlineKeyboardMarkup:
    """Get preview navigation keyboard."""
    nav_buttons = []

    # Previous button
    if current_page > 1:
        nav_buttons.append(
            InlineKeyboardButton(
                f"<< {get_button_text('previous', lang)}",
                callback_data=f"preview_page_{current_page - 1}",
            )
        )

    # Page indicator
    nav_buttons.append(
        InlineKeyboardButton(
            f"{current_page}/{total_pages}",
            callback_data="preview_current",  # No action
        )
    )

    # Next button
    if current_page < total_pages:
        nav_buttons.append(
            InlineKeyboardButton(
                f"{get_button_text('next', lang)} >>",
                callback_data=f"preview_page_{current_page + 1}",
            )
        )

    buttons = [nav_buttons]

    # Action buttons
    buttons.append(
        [
            InlineKeyboardButton(
                get_button_text("edit", lang), callback_data="action_edit"
            ),
            InlineKeyboardButton(
                get_button_text("done", lang), callback_data="action_done"
            ),
        ]
    )

    buttons.append(
        [
            InlineKeyboardButton(
                get_button_text("back", lang), callback_data="action_back"
            )
        ]
    )

    return InlineKeyboardMarkup(buttons)


def get_confirm_menu(lang: str = "en") -> InlineKeyboardMarkup:
    """Get yes/no confirmation keyboard."""
    return InlineKeyboardMarkup(
        [
            [
                InlineKeyboardButton(
                    get_button_text("yes", lang), callback_data="confirm_yes"
                ),
                InlineKeyboardButton(
                    get_button_text("no", lang), callback_data="confirm_no"
                ),
            ],
        ]
    )


def get_confirm_done_menu(
    lang: str = "en", file_type: str = "docx"
) -> InlineKeyboardMarkup:
    """Get confirmation menu for completing session."""
    return InlineKeyboardMarkup(
        [
            [
                InlineKeyboardButton(
                    get_button_text("confirm", lang) + f" (.{file_type})",
                    callback_data="done_confirm",
                )
            ],
            [
                InlineKeyboardButton(
                    get_button_text("cancel", lang), callback_data="action_cancel"
                )
            ],
        ]
    )


def get_language_menu() -> InlineKeyboardMarkup:
    """Get language selection keyboard."""
    return InlineKeyboardMarkup(
        [
            [InlineKeyboardButton("English", callback_data="lang_en")],
            [InlineKeyboardButton("Bahasa Indonesia", callback_data="lang_id")],
        ]
    )


def get_cancel_button(lang: str = "en") -> InlineKeyboardMarkup:
    """Get single cancel button keyboard."""
    return InlineKeyboardMarkup(
        [
            [
                InlineKeyboardButton(
                    get_button_text("cancel", lang), callback_data="action_cancel"
                )
            ],
        ]
    )


def get_back_button(lang: str = "en") -> InlineKeyboardMarkup:
    """Get single back button keyboard."""
    return InlineKeyboardMarkup(
        [
            [
                InlineKeyboardButton(
                    get_button_text("back", lang), callback_data="action_back"
                )
            ],
        ]
    )


def get_translate_target_menu(lang: str = "en") -> InlineKeyboardMarkup:
    """Get translation target language selection."""
    return InlineKeyboardMarkup(
        [
            [
                InlineKeyboardButton("English", callback_data="translate_to_en"),
                InlineKeyboardButton("Indonesian", callback_data="translate_to_id"),
            ],
            [
                InlineKeyboardButton("Spanish", callback_data="translate_to_es"),
                InlineKeyboardButton("Chinese", callback_data="translate_to_zh"),
            ],
            [
                InlineKeyboardButton("Japanese", callback_data="translate_to_ja"),
                InlineKeyboardButton("Korean", callback_data="translate_to_ko"),
            ],
            [
                InlineKeyboardButton(
                    get_button_text("cancel", lang), callback_data="action_cancel"
                )
            ],
        ]
    )


def get_after_action_menu(lang: str = "en") -> InlineKeyboardMarkup:
    """Get menu shown after an action is completed."""
    return InlineKeyboardMarkup(
        [
            [
                InlineKeyboardButton(
                    get_button_text("preview", lang), callback_data="action_preview"
                ),
                InlineKeyboardButton(
                    get_button_text("edit", lang), callback_data="action_edit"
                ),
            ],
            [
                InlineKeyboardButton(
                    get_button_text("done", lang), callback_data="action_done"
                ),
            ],
        ]
    )
