"""
Markdown to DOCX renderer.

Converts markdown-formatted text to properly formatted python-docx Document.
Supports: headings, bold, italic, code, lists, horizontal rules.
"""

import re
import logging
from typing import Optional

from docx import Document
from docx.shared import Pt, RGBColor
from docx.enum.text import WD_ALIGN_PARAGRAPH

logger = logging.getLogger(__name__)

# Heading font sizes
HEADING_SIZES = {
    1: 24,
    2: 18,
    3: 14,
    4: 12,
    5: 11,
    6: 11,
}

# Default font size for body text
DEFAULT_FONT_SIZE = 11

# Monospace font for code
CODE_FONT = "Courier New"


def render_markdown_to_docx(doc: Document, content: str) -> None:
    """
    Render markdown content to a python-docx Document.

    Supported markdown:
    - # Heading 1, ## Heading 2, ### Heading 3, etc.
    - **bold**, *italic*, ***bold italic***
    - `inline code`
    - ``` code blocks ```
    - - unordered lists, * unordered lists
    - 1. ordered lists
    - --- horizontal rules

    Args:
        doc: python-docx Document object
        content: Markdown-formatted text

    Note:
        If parsing fails, content is rendered as plain text with a warning logged.
    """
    try:
        _render_content(doc, content)
    except Exception as e:
        logger.warning(f"Markdown parsing failed, rendering as plain text: {e}")
        # Fallback: render as plain text
        for paragraph in content.split("\n\n"):
            if paragraph.strip():
                p = doc.add_paragraph()
                run = p.add_run(paragraph.strip())
                run.font.size = Pt(DEFAULT_FONT_SIZE)


def _render_content(doc: Document, content: str) -> None:
    """
    Internal function to parse and render markdown content.

    Args:
        doc: python-docx Document object
        content: Markdown-formatted text
    """
    lines = content.split("\n")
    i = 0
    in_code_block = False
    code_block_lines = []

    while i < len(lines):
        line = lines[i]

        # Handle code blocks
        if line.strip().startswith("```"):
            if in_code_block:
                # End of code block
                _add_code_block(doc, "\n".join(code_block_lines))
                code_block_lines = []
                in_code_block = False
            else:
                # Start of code block
                in_code_block = True
            i += 1
            continue

        if in_code_block:
            code_block_lines.append(line)
            i += 1
            continue

        # Skip empty lines
        if not line.strip():
            i += 1
            continue

        # Horizontal rule
        if line.strip() in ("---", "***", "___", "- - -", "* * *"):
            _add_horizontal_rule(doc)
            i += 1
            continue

        # Heading
        heading_match = re.match(r"^(#{1,6})\s+(.+)$", line)
        if heading_match:
            level = len(heading_match.group(1))
            text = heading_match.group(2)
            _add_heading(doc, text, level)
            i += 1
            continue

        # Unordered list item
        if re.match(r"^[\s]*[-*+]\s+", line):
            # Collect consecutive list items
            list_items = []
            while i < len(lines) and re.match(r"^[\s]*[-*+]\s+", lines[i]):
                item_text = re.sub(r"^[\s]*[-*+]\s+", "", lines[i])
                list_items.append(item_text)
                i += 1
            _add_unordered_list(doc, list_items)
            continue

        # Ordered list item
        if re.match(r"^[\s]*\d+\.\s+", line):
            # Collect consecutive list items
            list_items = []
            while i < len(lines) and re.match(r"^[\s]*\d+\.\s+", lines[i]):
                item_text = re.sub(r"^[\s]*\d+\.\s+", "", lines[i])
                list_items.append(item_text)
                i += 1
            _add_ordered_list(doc, list_items)
            continue

        # Regular paragraph - collect lines until empty line or block element
        para_lines = [line]
        i += 1
        while i < len(lines):
            next_line = lines[i]
            # Stop at empty line
            if not next_line.strip():
                break
            # Stop at block elements
            if (
                next_line.strip().startswith("#")
                or next_line.strip().startswith("```")
                or next_line.strip() in ("---", "***", "___", "- - -", "* * *")
                or re.match(r"^[\s]*[-*+]\s+", next_line)
                or re.match(r"^[\s]*\d+\.\s+", next_line)
            ):
                break
            para_lines.append(next_line)
            i += 1

        # Render paragraph with inline formatting
        _add_paragraph(doc, " ".join(para_lines))


def _add_heading(doc: Document, text: str, level: int) -> None:
    """Add a heading to the document."""
    p = doc.add_paragraph()
    # Parse inline formatting in heading
    _add_formatted_runs(p, text)
    # Make all runs bold and set size
    font_size = HEADING_SIZES.get(level, DEFAULT_FONT_SIZE)
    for run in p.runs:
        run.bold = True
        run.font.size = Pt(font_size)


def _add_paragraph(doc: Document, text: str) -> None:
    """Add a paragraph with inline formatting."""
    p = doc.add_paragraph()
    _add_formatted_runs(p, text)


def _add_formatted_runs(paragraph, text: str) -> None:
    """
    Parse inline markdown formatting and add runs to paragraph.

    Supports:
    - ***bold italic*** or ___bold italic___
    - **bold** or __bold__
    - *italic* or _italic_
    - `code`
    """
    # Pattern to match inline formatting
    # Order matters: check triple first, then double, then single
    pattern = (
        r"(\*\*\*(.+?)\*\*\*|___(.+?)___|"
        r"\*\*(.+?)\*\*|__(.+?)__|"
        r"\*(.+?)\*|_([^_]+)_|"
        r"`([^`]+)`|"
        r"([^*_`]+))"
    )

    pos = 0
    text_remaining = text

    while text_remaining:
        match = re.search(pattern, text_remaining)

        if not match:
            # No more patterns, add remaining text
            if text_remaining:
                run = paragraph.add_run(text_remaining)
                run.font.size = Pt(DEFAULT_FONT_SIZE)
            break

        # Add text before match
        if match.start() > 0:
            before_text = text_remaining[: match.start()]
            run = paragraph.add_run(before_text)
            run.font.size = Pt(DEFAULT_FONT_SIZE)

        # Determine which group matched
        if match.group(2) or match.group(3):
            # ***bold italic*** or ___bold italic___
            content = match.group(2) or match.group(3)
            run = paragraph.add_run(content)
            run.bold = True
            run.italic = True
        elif match.group(4) or match.group(5):
            # **bold** or __bold__
            content = match.group(4) or match.group(5)
            run = paragraph.add_run(content)
            run.bold = True
        elif match.group(6) or match.group(7):
            # *italic* or _italic_
            content = match.group(6) or match.group(7)
            run = paragraph.add_run(content)
            run.italic = True
        elif match.group(8):
            # `code`
            content = match.group(8)
            run = paragraph.add_run(content)
            run.font.name = CODE_FONT
        elif match.group(9):
            # Plain text
            content = match.group(9)
            run = paragraph.add_run(content)

        run.font.size = Pt(DEFAULT_FONT_SIZE)

        # Move past this match
        text_remaining = text_remaining[match.end() :]


def _add_code_block(doc: Document, code: str) -> None:
    """Add a code block to the document."""
    p = doc.add_paragraph()
    run = p.add_run(code)
    run.font.name = CODE_FONT
    run.font.size = Pt(10)
    # Light gray background would be nice but requires more complex formatting
    # Just use monospace font for now


def _add_horizontal_rule(doc: Document) -> None:
    """Add a horizontal rule to the document."""
    p = doc.add_paragraph()
    run = p.add_run("─" * 50)
    run.font.size = Pt(DEFAULT_FONT_SIZE)
    p.alignment = WD_ALIGN_PARAGRAPH.CENTER


def _add_unordered_list(doc: Document, items: list[str]) -> None:
    """Add an unordered (bullet) list to the document."""
    for item in items:
        p = doc.add_paragraph(style="List Bullet")
        _add_formatted_runs(p, item)


def _add_ordered_list(doc: Document, items: list[str]) -> None:
    """Add an ordered (numbered) list to the document."""
    for item in items:
        p = doc.add_paragraph(style="List Number")
        _add_formatted_runs(p, item)
