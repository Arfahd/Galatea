"""
File operations service for handling document read/write/edit.
Supports PDF, DOCX, TXT, XLSX, and PPTX formats.
"""

import logging
import aiofiles
import json
from pathlib import Path
from typing import Optional
from io import BytesIO

from docx import Document
from docx.shared import Pt
from pypdf import PdfReader
import pdfplumber
from reportlab.lib.pagesizes import letter
from reportlab.pdfgen import canvas
from reportlab.lib.units import inch
from openpyxl import Workbook, load_workbook
from openpyxl.utils import get_column_letter
from pptx import Presentation
from pptx.util import Inches, Pt as PptxPt

from ..config import config
from ..templates.pptx_templates import get_pptx_template

logger = logging.getLogger(__name__)


class FileService:
    """Service for file operations (read, write, edit)."""

    def __init__(self):
        config.ensure_directories()

    def get_user_directory(self, user_id: int) -> Path:
        """
        Get or create user-specific directory with validation.

        Args:
            user_id: Telegram user ID (must be positive integer)

        Returns:
            Path to user's directory

        Raises:
            FileServiceError: If user_id is invalid or path traversal detected
        """
        # Validate user_id is a positive integer
        if not isinstance(user_id, int) or user_id <= 0:
            raise FileServiceError(f"Invalid user ID: {user_id}")

        user_dir = config.USER_FILES_DIR / str(user_id)

        # Ensure the resolved path is under USER_FILES_DIR (prevent traversal)
        try:
            resolved = user_dir.resolve()
            base_resolved = config.USER_FILES_DIR.resolve()
            if not str(resolved).startswith(str(base_resolved)):
                logger.error(f"Path traversal attempt detected for user {user_id}")
                raise FileServiceError("Invalid user directory path")
        except (OSError, ValueError) as e:
            logger.error(f"Path resolution error for user {user_id}: {e}")
            raise FileServiceError("Invalid user directory path")

        user_dir.mkdir(parents=True, exist_ok=True)
        return user_dir

    # ==================== General File Operations ====================

    async def read_file(self, file_path: Path) -> str:
        """
        Read content from a file based on its extension.

        Args:
            file_path: Path to the file

        Returns:
            File content as string
        """
        extension = file_path.suffix.lower()

        if extension == ".pdf":
            return await self._read_pdf(file_path)
        elif extension in {".docx", ".doc"}:
            return await self._read_docx(file_path)
        elif extension == ".txt":
            return await self._read_txt(file_path)
        elif extension == ".xlsx":
            return await self._read_xlsx(file_path)
        elif extension == ".pptx":
            return await self._read_pptx(file_path)
        else:
            raise FileServiceError(f"Unsupported file type: {extension}")

    async def read_file_from_bytes(self, file_bytes: bytes, filename: str) -> str:
        """
        Read content from file bytes.

        Args:
            file_bytes: Raw file bytes
            filename: Original filename for extension detection

        Returns:
            File content as string
        """
        extension = Path(filename).suffix.lower()

        if extension == ".pdf":
            return self._read_pdf_bytes(file_bytes)
        elif extension in {".docx", ".doc"}:
            return self._read_docx_bytes(file_bytes)
        elif extension == ".txt":
            return file_bytes.decode("utf-8", errors="replace")
        elif extension == ".xlsx":
            return self._read_xlsx_bytes(file_bytes)
        elif extension == ".pptx":
            return self._read_pptx_bytes(file_bytes)
        else:
            raise FileServiceError(f"Unsupported file type: {extension}")

    async def write_file(
        self, content: str, filename: str, user_id: int, file_format: str = "txt"
    ) -> Path:
        """
        Write content to a file.

        Args:
            content: Content to write
            filename: Desired filename (without extension)
            user_id: User ID for directory organization
            file_format: Output format (txt, docx, pdf, xlsx, pptx)

        Returns:
            Path to the created file
        """
        user_dir = self.get_user_directory(user_id)

        # Sanitize filename
        safe_filename = self._sanitize_filename(filename)

        if file_format == "txt":
            return await self._write_txt(content, safe_filename, user_dir)
        elif file_format == "docx":
            return await self._write_docx(content, safe_filename, user_dir)
        elif file_format == "pdf":
            return await self._write_pdf(content, safe_filename, user_dir)
        elif file_format == "xlsx":
            return await self._write_xlsx(content, safe_filename, user_dir)
        elif file_format == "pptx":
            return await self._write_pptx(content, safe_filename, user_dir)
        else:
            raise FileServiceError(f"Unsupported output format: {file_format}")

    async def save_uploaded_file(
        self, file_bytes: bytes, filename: str, user_id: int
    ) -> Path:
        """
        Save an uploaded file to user's directory.

        Args:
            file_bytes: Raw file bytes
            filename: Original filename
            user_id: User ID

        Returns:
            Path to saved file
        """
        user_dir = self.get_user_directory(user_id)
        safe_filename = self._sanitize_filename(filename)
        file_path = user_dir / safe_filename

        # Handle duplicate filenames
        counter = 1
        while file_path.exists():
            stem = Path(safe_filename).stem
            suffix = Path(safe_filename).suffix
            file_path = user_dir / f"{stem}_{counter}{suffix}"
            counter += 1

        async with aiofiles.open(file_path, "wb") as f:
            await f.write(file_bytes)

        logger.info(f"Saved file: {file_path}")
        return file_path

    def list_user_files(self, user_id: int) -> list[Path]:
        """List all files for a user."""
        user_dir = self.get_user_directory(user_id)
        return [
            f
            for f in user_dir.iterdir()
            if f.is_file() and f.suffix.lower() in config.SUPPORTED_EXTENSIONS
        ]

    async def delete_file(self, file_path: Path) -> bool:
        """Delete a file."""
        try:
            if file_path.exists():
                file_path.unlink()
                logger.info(f"Deleted file: {file_path}")
                return True
            return False
        except Exception as e:
            logger.error(f"Error deleting file {file_path}: {e}")
            return False

    async def cleanup_user_directory(self, user_id: int) -> int:
        """
        Delete all files in user's directory.

        Args:
            user_id: User ID

        Returns:
            Number of files deleted
        """
        user_dir = self.get_user_directory(user_id)
        count = 0

        try:
            for file_path in user_dir.iterdir():
                if file_path.is_file():
                    file_path.unlink()
                    count += 1
            logger.info(f"Cleaned up {count} files for user {user_id}")
        except Exception as e:
            logger.error(f"Error cleaning up user directory {user_id}: {e}")

        return count

    def get_file_size_str(self, file_path: Path) -> str:
        """Get human-readable file size."""
        if not file_path.exists():
            return "Unknown"

        size = file_path.stat().st_size
        for unit in ["B", "KB", "MB", "GB"]:
            if size < 1024:
                return f"{size:.1f} {unit}"
            size /= 1024
        return f"{size:.1f} TB"

    # ==================== PDF Operations ====================

    async def _read_pdf(self, file_path: Path) -> str:
        """Read PDF file."""
        async with aiofiles.open(file_path, "rb") as f:
            content = await f.read()
        return self._read_pdf_bytes(content)

    def _read_pdf_bytes(self, file_bytes: bytes) -> str:
        """
        Read PDF from bytes using pdfplumber (primary) with OCR fallback.

        Strategy:
        1. Try pdfplumber first (better table extraction)
        2. If text is too short, try pypdf as fallback
        3. If still too short and OCR is enabled, try Tesseract OCR
        """
        text_parts = []
        total_text_length = 0

        # Try pdfplumber first (better for tables and complex layouts)
        try:
            with pdfplumber.open(BytesIO(file_bytes)) as pdf:
                for page_num, page in enumerate(pdf.pages, 1):
                    text = page.extract_text() or ""

                    # Also extract tables if present
                    tables = page.extract_tables()
                    table_text = ""
                    if tables:
                        for table in tables:
                            if table:
                                table_rows = []
                                for row in table:
                                    row_text = "\t".join(
                                        str(cell) if cell else "" for cell in row
                                    )
                                    table_rows.append(row_text)
                                table_text += (
                                    "\n[Table]\n" + "\n".join(table_rows) + "\n"
                                )

                    combined_text = text + table_text
                    if combined_text.strip():
                        text_parts.append(
                            f"--- Page {page_num} ---\n{combined_text.strip()}"
                        )
                        total_text_length += len(combined_text)

        except Exception as e:
            logger.warning(f"pdfplumber failed, trying pypdf: {e}")
            # Fall back to pypdf
            try:
                reader = PdfReader(BytesIO(file_bytes))
                for page_num, page in enumerate(reader.pages, 1):
                    text = page.extract_text()
                    if text:
                        text_parts.append(f"--- Page {page_num} ---\n{text}")
                        total_text_length += len(text)
            except Exception as e2:
                logger.error(f"pypdf also failed: {e2}")

        # Check if we need OCR (text too short, might be scanned PDF)
        if total_text_length < config.OCR_MIN_TEXT_THRESHOLD and config.OCR_ENABLED:
            logger.info(
                f"PDF text length ({total_text_length}) below threshold, attempting OCR"
            )
            ocr_text = self._ocr_pdf_bytes(file_bytes)
            if ocr_text:
                return ocr_text

        if text_parts:
            return "\n\n".join(text_parts)

        return "(No text content found in PDF)"

    def _ocr_pdf_bytes(self, file_bytes: bytes) -> Optional[str]:
        """
        Perform OCR on PDF bytes using Tesseract.
        Lazy-loads OCR dependencies to save memory.

        Returns:
            Extracted text or None if OCR fails/unavailable
        """
        try:
            # Lazy import to save memory when OCR not needed
            import pytesseract
            from pdf2image import convert_from_bytes
        except ImportError as e:
            logger.warning(f"OCR dependencies not available: {e}")
            return None

        try:
            # Check if Tesseract is installed
            pytesseract.get_tesseract_version()
        except Exception as e:
            logger.warning(f"Tesseract not installed or not found: {e}")
            return None

        try:
            # Convert PDF pages to images
            # Use lower DPI (150) to balance quality vs memory on 4GB VPS
            images = convert_from_bytes(file_bytes, dpi=150)

            text_parts = []
            for page_num, image in enumerate(images, 1):
                # Perform OCR with configured languages
                text = pytesseract.image_to_string(image, lang=config.OCR_LANGUAGES)
                if text.strip():
                    text_parts.append(f"--- Page {page_num} (OCR) ---\n{text.strip()}")

            if text_parts:
                logger.info(f"OCR extracted text from {len(text_parts)} pages")
                return "\n\n".join(text_parts)

            return None

        except Exception as e:
            logger.error(f"OCR failed: {e}", exc_info=True)
            return None

    async def _write_pdf(self, content: str, filename: str, user_dir: Path) -> Path:
        """Write PDF file."""
        if not filename.endswith(".pdf"):
            filename += ".pdf"

        file_path = user_dir / filename

        c = canvas.Canvas(str(file_path), pagesize=letter)
        width, height = letter

        # Set up text formatting
        c.setFont("Helvetica", 11)

        # Split content into lines and write
        y_position = height - inch
        line_height = 14
        margin = inch
        max_width = width - 2 * margin

        lines = content.split("\n")

        for line in lines:
            # Simple word wrapping
            words = line.split()
            current_line = ""

            for word in words:
                test_line = f"{current_line} {word}".strip()
                if c.stringWidth(test_line, "Helvetica", 11) < max_width:
                    current_line = test_line
                else:
                    if current_line:
                        c.drawString(margin, y_position, current_line)
                        y_position -= line_height

                        if y_position < inch:
                            c.showPage()
                            c.setFont("Helvetica", 11)
                            y_position = height - inch

                    current_line = word

            if current_line:
                c.drawString(margin, y_position, current_line)
                y_position -= line_height

                if y_position < inch:
                    c.showPage()
                    c.setFont("Helvetica", 11)
                    y_position = height - inch

        c.save()
        return file_path

    # ==================== DOCX Operations ====================

    async def _read_docx(self, file_path: Path) -> str:
        """Read DOCX file."""
        async with aiofiles.open(file_path, "rb") as f:
            content = await f.read()
        return self._read_docx_bytes(content)

    def _read_docx_bytes(self, file_bytes: bytes) -> str:
        """Read DOCX from bytes."""
        try:
            doc = Document(BytesIO(file_bytes))
            paragraphs = [para.text for para in doc.paragraphs if para.text.strip()]
            return (
                "\n\n".join(paragraphs)
                if paragraphs
                else "(No text content found in document)"
            )
        except Exception as e:
            logger.error(f"Error reading DOCX: {e}")
            raise FileServiceError(f"Failed to read DOCX: {str(e)}")

    async def _write_docx(self, content: str, filename: str, user_dir: Path) -> Path:
        """
        Write DOCX file with markdown formatting support.

        Supports: headings, bold, italic, code, lists, horizontal rules.
        """
        if not filename.endswith(".docx"):
            filename += ".docx"

        file_path = user_dir / filename

        doc = Document()

        # Render markdown to DOCX with proper formatting
        from ..utils.markdown_docx import render_markdown_to_docx

        render_markdown_to_docx(doc, content)

        doc.save(str(file_path))
        return file_path

    # ==================== TXT Operations ====================

    async def _read_txt(self, file_path: Path) -> str:
        """Read TXT file."""
        try:
            async with aiofiles.open(file_path, "r", encoding="utf-8") as f:
                return await f.read()
        except UnicodeDecodeError:
            async with aiofiles.open(file_path, "r", encoding="latin-1") as f:
                return await f.read()

    async def _write_txt(self, content: str, filename: str, user_dir: Path) -> Path:
        """Write TXT file."""
        if not filename.endswith(".txt"):
            filename += ".txt"

        file_path = user_dir / filename
        async with aiofiles.open(file_path, "w", encoding="utf-8") as f:
            await f.write(content)

        return file_path

    # ==================== XLSX (Excel) Operations ====================

    async def _read_xlsx(self, file_path: Path) -> str:
        """Read XLSX file."""
        async with aiofiles.open(file_path, "rb") as f:
            content = await f.read()
        return self._read_xlsx_bytes(content)

    def _read_xlsx_bytes(self, file_bytes: bytes) -> str:
        """Read XLSX from bytes."""
        try:
            wb = load_workbook(BytesIO(file_bytes))
            result_parts = []

            for sheet_name in wb.sheetnames:
                sheet = wb[sheet_name]
                result_parts.append(f"=== Sheet: {sheet_name} ===")

                rows = []
                for row in sheet.iter_rows():
                    row_values = []
                    for cell in row:
                        value = cell.value
                        if value is not None:
                            row_values.append(str(value))
                        else:
                            row_values.append("")

                    # Only add row if it has content
                    if any(v.strip() for v in row_values):
                        rows.append("\t".join(row_values))

                if rows:
                    result_parts.append("\n".join(rows))
                else:
                    result_parts.append("(Empty sheet)")

                result_parts.append("")

            return "\n".join(result_parts) if result_parts else "(Empty spreadsheet)"
        except Exception as e:
            logger.error(f"Error reading XLSX: {e}")
            raise FileServiceError(f"Failed to read XLSX: {str(e)}")

    async def _write_xlsx(self, content: str, filename: str, user_dir: Path) -> Path:
        """
        Write XLSX file from text content.
        Content format: tab-separated values, sheets separated by === Sheet: name ===
        """
        if not filename.endswith(".xlsx"):
            filename += ".xlsx"

        file_path = user_dir / filename

        wb = Workbook()
        # Remove default sheet
        default_sheet = wb.active

        # Parse content
        sheets_data = self._parse_xlsx_content(content)

        if not sheets_data:
            # Just create a sheet with the content as rows
            ws = default_sheet
            ws.title = "Sheet1"
            for row_idx, line in enumerate(content.split("\n"), 1):
                if line.strip():
                    for col_idx, value in enumerate(line.split("\t"), 1):
                        ws.cell(row=row_idx, column=col_idx, value=value)
        else:
            # Create sheets from parsed data
            first = True
            for sheet_name, rows in sheets_data.items():
                if first:
                    ws = default_sheet
                    ws.title = sheet_name
                    first = False
                else:
                    ws = wb.create_sheet(sheet_name)

                for row_idx, row_data in enumerate(rows, 1):
                    for col_idx, value in enumerate(row_data, 1):
                        ws.cell(row=row_idx, column=col_idx, value=value)

        wb.save(str(file_path))
        return file_path

    def _parse_xlsx_content(self, content: str) -> dict:
        """Parse text content into sheets data structure."""
        sheets = {}
        current_sheet = None
        current_rows = []

        for line in content.split("\n"):
            if line.startswith("=== Sheet:") and line.endswith("==="):
                # Save previous sheet
                if current_sheet:
                    sheets[current_sheet] = current_rows

                # Start new sheet
                sheet_name = line.replace("=== Sheet:", "").replace("===", "").strip()
                current_sheet = sheet_name
                current_rows = []
            elif current_sheet and line.strip() and not line.startswith("(Empty"):
                # Add row to current sheet
                row_data = line.split("\t")
                current_rows.append(row_data)

        # Save last sheet
        if current_sheet:
            sheets[current_sheet] = current_rows

        return sheets

    def get_xlsx_structure(self, file_bytes: bytes) -> dict:
        """Get structure of XLSX file (sheets, dimensions)."""
        try:
            wb = load_workbook(BytesIO(file_bytes))
            structure = {"sheets": []}

            for sheet_name in wb.sheetnames:
                sheet = wb[sheet_name]
                structure["sheets"].append(
                    {
                        "name": sheet_name,
                        "dimensions": sheet.dimensions,
                        "max_row": sheet.max_row,
                        "max_column": sheet.max_column,
                    }
                )

            return structure
        except Exception as e:
            logger.error(f"Error getting XLSX structure: {e}")
            return {"sheets": []}

    # ==================== PPTX (PowerPoint) Operations ====================

    async def _read_pptx(self, file_path: Path) -> str:
        """Read PPTX file."""
        async with aiofiles.open(file_path, "rb") as f:
            content = await f.read()
        return self._read_pptx_bytes(content)

    def _read_pptx_bytes(self, file_bytes: bytes) -> str:
        """Read PPTX from bytes, including speaker notes."""
        try:
            prs = Presentation(BytesIO(file_bytes))
            result_parts = []

            for slide_num, slide in enumerate(prs.slides, 1):
                result_parts.append(f"--- Slide {slide_num} ---")

                texts = []
                for shape in slide.shapes:
                    if hasattr(shape, "text") and shape.text.strip():
                        texts.append(shape.text.strip())

                if texts:
                    result_parts.append("\n".join(texts))
                else:
                    result_parts.append("(No text content)")

                # Extract speaker notes if present
                if slide.has_notes_slide:
                    notes_slide = slide.notes_slide
                    notes_text = notes_slide.notes_text_frame.text.strip()
                    if notes_text:
                        result_parts.append(f"\n[Speaker Notes]\n{notes_text}")

                result_parts.append("")

            return "\n".join(result_parts) if result_parts else "(Empty presentation)"
        except Exception as e:
            logger.error(f"Error reading PPTX: {e}")
            raise FileServiceError(f"Failed to read PPTX: {str(e)}")

    async def _write_pptx(self, content: str, filename: str, user_dir: Path) -> Path:
        """
        Write PPTX file from text content.
        Content format: slides separated by --- Slide N ---
        """
        if not filename.endswith(".pptx"):
            filename += ".pptx"

        file_path = user_dir / filename

        prs = Presentation()

        # Parse slides from content
        slides_data = self._parse_pptx_content(content)

        if not slides_data:
            # Create a single slide with title
            slide_layout = prs.slide_layouts[6]  # Blank layout
            slide = prs.slides.add_slide(slide_layout)

            # Add text box with content
            left = Inches(0.5)
            top = Inches(0.5)
            width = Inches(9)
            height = Inches(6)

            txBox = slide.shapes.add_textbox(left, top, width, height)
            tf = txBox.text_frame
            tf.text = content[:1000] if len(content) > 1000 else content
        else:
            for slide_data in slides_data:
                self._add_slide_from_data(prs, slide_data)

        prs.save(str(file_path))
        return file_path

    async def write_pptx_from_template(
        self, template_key: str, filename: str, user_id: int, lang: str = "en"
    ) -> Path:
        """
        Create PPTX from a template.

        Args:
            template_key: Template identifier
            filename: Output filename
            user_id: User ID
            lang: Language for content

        Returns:
            Path to created file
        """
        template = get_pptx_template(template_key)
        if not template:
            raise FileServiceError(f"Template not found: {template_key}")

        user_dir = self.get_user_directory(user_id)
        safe_filename = self._sanitize_filename(filename)
        if not safe_filename.endswith(".pptx"):
            safe_filename += ".pptx"

        file_path = user_dir / safe_filename

        prs = Presentation()

        for slide_def in template["slides"]:
            self._add_slide_from_template(prs, slide_def, lang)

        prs.save(str(file_path))
        logger.info(f"Created PPTX from template {template_key}: {file_path}")
        return file_path

    def _parse_pptx_content(self, content: str) -> list[dict]:
        """Parse text content into slides data structure."""
        slides = []
        current_slide = None
        current_content = []

        for line in content.split("\n"):
            if line.startswith("--- Slide") and line.endswith("---"):
                # Save previous slide
                if current_slide is not None:
                    slides.append(
                        {
                            "title": current_slide,
                            "content": "\n".join(current_content).strip(),
                        }
                    )

                # Extract slide info
                slide_info = line.replace("---", "").strip()
                current_slide = slide_info
                current_content = []
            elif (
                current_slide is not None and line.strip() and not line.startswith("(")
            ):
                current_content.append(line)

        # Save last slide
        if current_slide is not None:
            slides.append(
                {"title": current_slide, "content": "\n".join(current_content).strip()}
            )

        return slides

    def _add_slide_from_data(self, prs: Presentation, slide_data: dict) -> None:
        """Add a slide to presentation from data dict."""
        # Use title and content layout
        slide_layout = prs.slide_layouts[1]  # Title and Content
        slide = prs.slides.add_slide(slide_layout)

        # Set title if exists
        title_shape = slide.shapes.title
        if title_shape:
            title = slide_data.get("title", "")
            # Clean up title (remove "Slide N:" prefix if present)
            if ":" in title:
                title = title.split(":", 1)[1].strip()
            title_shape.text = title

        # Add content
        content = slide_data.get("content", "")
        if content and len(slide.placeholders) > 1:
            body_placeholder = slide.placeholders[1]
            body_placeholder.text = content

    def _add_slide_from_template(
        self, prs: Presentation, slide_def: dict, lang: str = "en"
    ) -> None:
        """Add a slide from template definition."""
        layout_type = slide_def.get("layout", "content")

        if layout_type == "title":
            slide_layout = prs.slide_layouts[0]  # Title Slide
            slide = prs.slides.add_slide(slide_layout)

            title = slide_def.get(f"title_{lang}", slide_def.get("title_en", ""))
            subtitle = slide_def.get(
                f"subtitle_{lang}", slide_def.get("subtitle_en", "")
            )

            if slide.shapes.title:
                slide.shapes.title.text = title

            # Find subtitle placeholder
            for shape in slide.placeholders:
                if shape.placeholder_format.idx == 1:  # Subtitle
                    shape.text = subtitle
                    break
        else:
            slide_layout = prs.slide_layouts[1]  # Title and Content
            slide = prs.slides.add_slide(slide_layout)

            title = slide_def.get(f"title_{lang}", slide_def.get("title_en", ""))
            content = slide_def.get(f"content_{lang}", slide_def.get("content_en", ""))

            if slide.shapes.title:
                slide.shapes.title.text = title

            # Add content to body placeholder
            if content and len(slide.placeholders) > 1:
                body_placeholder = slide.placeholders[1]
                body_placeholder.text = content

    def get_pptx_structure(self, file_bytes: bytes) -> dict:
        """Get structure of PPTX file (slide count, titles)."""
        try:
            prs = Presentation(BytesIO(file_bytes))
            structure = {"slide_count": len(prs.slides), "slides": []}

            for i, slide in enumerate(prs.slides, 1):
                slide_info = {"number": i, "title": ""}
                if slide.shapes.title:
                    slide_info["title"] = slide.shapes.title.text
                structure["slides"].append(slide_info)

            return structure
        except Exception as e:
            logger.error(f"Error getting PPTX structure: {e}")
            return {"slide_count": 0, "slides": []}

    # ==================== Utility Methods ====================

    def _sanitize_filename(self, filename: str) -> str:
        """Sanitize filename to prevent path traversal and invalid characters."""
        # Remove path components
        filename = Path(filename).name

        # Replace problematic characters
        invalid_chars = '<>:"/\\|?*'
        for char in invalid_chars:
            filename = filename.replace(char, "_")

        # Limit length
        if len(filename) > 200:
            stem = Path(filename).stem[:190]
            suffix = Path(filename).suffix
            filename = f"{stem}{suffix}"

        return filename


class FileServiceError(Exception):
    """Custom exception for file service errors."""

    pass
