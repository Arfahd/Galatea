"""
Document analysis service for generating todos and recommendations.
Uses Claude AI to analyze documents and provide actionable suggestions.
"""

import logging
import json
import re
from typing import Optional

from ..config import config
from ..models.todo_item import TodoItem

logger = logging.getLogger(__name__)


class AnalysisService:
    """Service for analyzing documents and generating todos/suggestions."""

    def __init__(self, claude_service):
        """
        Initialize analysis service.

        Args:
            claude_service: Instance of ClaudeService for AI processing
        """
        self.claude_service = claude_service
        self.max_todos = config.MAX_TODOS

    async def analyze_document(
        self,
        content: str,
        file_type: str,
        language: str = "en",
        file_name: Optional[str] = None,
    ) -> list[TodoItem]:
        """
        Analyze a document and generate todo suggestions.

        Args:
            content: Document content
            file_type: Type of document (docx, pdf, xlsx, pptx)
            language: User's language preference
            file_name: Optional filename for context

        Returns:
            List of TodoItem suggestions
        """
        try:
            # Build analysis prompt based on file type
            prompt = self._build_analysis_prompt(
                content, file_type, language, file_name
            )

            # Get AI analysis
            response = await self.claude_service.analyze_for_todos(
                prompt=prompt,
                max_todos=self.max_todos,
            )

            # Parse todos from response
            todos = self._parse_todos_from_response(response)

            logger.info(f"Generated {len(todos)} todos for {file_type} document")
            return todos

        except Exception as e:
            logger.error(f"Error analyzing document: {e}")
            return []

    def _build_analysis_prompt(
        self,
        content: str,
        file_type: str,
        language: str,
        file_name: Optional[str],
    ) -> str:
        """Build the analysis prompt based on file type."""

        file_type_context = {
            "docx": "Word document",
            "pdf": "PDF document",
            "txt": "text document",
            "xlsx": "Excel spreadsheet",
            "pptx": "PowerPoint presentation",
        }

        doc_type = file_type_context.get(file_type, "document")

        prompt = f"""Analyze this {doc_type} and provide up to {self.max_todos} actionable suggestions for improvement.

Document name: {file_name or "Untitled"}

Content:
---
{content[:4000]}
---

For each suggestion, provide:
1. A clear description in English
2. A clear description in Indonesian
3. The type of action (edit, format, add, remove, fix, improve)
4. What specific part to target (e.g., "paragraph_2", "cell_A1", "slide_3")
5. Your specific suggestion or fix
6. Priority (1=highest, 5=lowest)

Focus on:"""

        # Add file-type specific analysis focus
        if file_type == "xlsx":
            prompt += """
- Data formatting consistency
- Missing or incomplete data
- Potential calculation errors
- Column/row organization
- Headers and labels"""
        elif file_type == "pptx":
            prompt += """
- Slide content clarity
- Presentation flow
- Missing key information
- Bullet point consistency
- Title effectiveness"""
        elif file_type in ["docx", "pdf", "txt"]:
            prompt += """
- Grammar and spelling
- Clarity and conciseness
- Structure and organization
- Missing information
- Tone consistency"""

        prompt += f"""

Respond with a JSON array of suggestions in this exact format:
{{
    "todos": [
        {{
            "description_en": "English description",
            "description_id": "Indonesian description",
            "action_type": "fix|edit|add|remove|format|improve",
            "target": "specific location",
            "suggestion": "the actual fix or content",
            "priority": 1-5
        }}
    ]
}}

User prefers responses in: {"Indonesian" if language == "id" else "English"}"""

        return prompt

    def _parse_todos_from_response(self, response: str) -> list[TodoItem]:
        """Parse TodoItems from AI response."""
        todos = []

        try:
            # Try to extract JSON from response
            json_match = re.search(r'\{[\s\S]*"todos"[\s\S]*\}', response)

            if json_match:
                json_str = json_match.group()
                data = json.loads(json_str)

                if "todos" in data and isinstance(data["todos"], list):
                    for item in data["todos"][: self.max_todos]:
                        try:
                            todo = TodoItem(
                                description_en=item.get("description_en", ""),
                                description_id=item.get(
                                    "description_id", item.get("description_en", "")
                                ),
                                action_type=item.get("action_type", "edit"),
                                target=item.get("target", ""),
                                suggestion=item.get("suggestion", ""),
                                priority=int(item.get("priority", 3)),
                            )
                            todos.append(todo)
                        except Exception as e:
                            logger.warning(f"Error parsing todo item: {e}")
                            continue
            else:
                # Fallback: try to parse as direct JSON array
                try:
                    data = json.loads(response)
                    if isinstance(data, list):
                        for item in data[: self.max_todos]:
                            todo = TodoItem.from_dict(item)
                            todos.append(todo)
                except json.JSONDecodeError:
                    logger.warning("Could not parse JSON from response")

        except Exception as e:
            logger.error(f"Error parsing todos from response: {e}")

        return todos

    async def execute_todo(
        self,
        todo: TodoItem,
        current_content: str,
        file_type: str,
    ) -> str:
        """
        Execute a todo item and return modified content.

        Args:
            todo: The TodoItem to execute
            current_content: Current document content
            file_type: Document type

        Returns:
            Modified content after applying the todo
        """
        try:
            prompt = f"""Apply this specific change to the document:

Action: {todo.action_type}
Target: {todo.target}
Suggestion: {todo.suggestion}
Description: {todo.description_en}

Current content:
---
{current_content}
---

Apply the change and return the complete modified content.
Only return the modified content, no explanations.
Wrap the content with [DOCUMENT_START] and [DOCUMENT_END] markers."""

            response = await self.claude_service.process_file_request(
                user_message=prompt,
                file_content=None,  # Already included in prompt
                file_name=None,
            )

            # Extract content from response
            modified_content = self.claude_service.extract_document_content(response)

            if modified_content:
                return modified_content
            else:
                # Return original if extraction failed
                return current_content

        except Exception as e:
            logger.error(f"Error executing todo: {e}")
            return current_content

    async def execute_all_todos(
        self,
        todos: list[TodoItem],
        current_content: str,
        file_type: str,
    ) -> str:
        """
        Execute all pending todos and return modified content.

        Args:
            todos: List of TodoItems to execute
            current_content: Current document content
            file_type: Document type

        Returns:
            Modified content after applying all todos
        """
        pending_todos = [t for t in todos if not t.executed]

        if not pending_todos:
            return current_content

        try:
            # Build combined prompt
            changes_description = "\n".join(
                [
                    f"- [{t.action_type}] {t.target}: {t.suggestion}"
                    for t in pending_todos
                ]
            )

            prompt = f"""Apply ALL these changes to the document:

{changes_description}

Current content:
---
{current_content}
---

Apply all changes and return the complete modified content.
Only return the modified content, no explanations.
Wrap the content with [DOCUMENT_START] and [DOCUMENT_END] markers."""

            response = await self.claude_service.process_file_request(
                user_message=prompt,
                file_content=None,
                file_name=None,
            )

            # Extract content from response
            modified_content = self.claude_service.extract_document_content(response)

            if modified_content:
                # Mark all as executed
                for todo in pending_todos:
                    todo.mark_executed()
                return modified_content
            else:
                return current_content

        except Exception as e:
            logger.error(f"Error executing all todos: {e}")
            return current_content

    def generate_quick_suggestions(
        self,
        content: str,
        file_type: str,
        language: str = "en",
    ) -> list[str]:
        """
        Generate quick suggestions without AI (rule-based).
        Used for immediate feedback while AI analysis runs.

        Args:
            content: Document content
            file_type: Document type
            language: User language

        Returns:
            List of suggestion strings
        """
        suggestions = []

        # Check content length
        if len(content) < 100:
            if language == "id":
                suggestions.append(
                    "Dokumen sangat pendek. Pertimbangkan untuk menambah konten."
                )
            else:
                suggestions.append(
                    "Document is very short. Consider adding more content."
                )

        # Check for common issues
        if file_type in ["docx", "pdf", "txt"]:
            # Check for multiple spaces
            if "  " in content:
                if language == "id":
                    suggestions.append(
                        "Ditemukan spasi ganda. Pertimbangkan untuk membersihkan format."
                    )
                else:
                    suggestions.append(
                        "Multiple spaces detected. Consider cleaning up formatting."
                    )

            # Check for very long paragraphs
            paragraphs = content.split("\n\n")
            for p in paragraphs:
                if len(p) > 1000:
                    if language == "id":
                        suggestions.append(
                            "Beberapa paragraf sangat panjang. Pertimbangkan untuk memecahnya."
                        )
                    else:
                        suggestions.append(
                            "Some paragraphs are very long. Consider breaking them up."
                        )
                    break

        elif file_type == "xlsx":
            # Check for empty header indicators
            if content.startswith("\t") or "\n\t" in content:
                if language == "id":
                    suggestions.append("Beberapa kolom mungkin tidak memiliki header.")
                else:
                    suggestions.append("Some columns may be missing headers.")

        elif file_type == "pptx":
            # Count slides
            slide_count = content.count("--- Slide")
            if slide_count < 3:
                if language == "id":
                    suggestions.append(
                        f"Presentasi hanya memiliki {slide_count} slide. Pertimbangkan untuk menambah lebih banyak."
                    )
                else:
                    suggestions.append(
                        f"Presentation has only {slide_count} slides. Consider adding more."
                    )

        return suggestions[:3]  # Return max 3 quick suggestions


class AnalysisServiceError(Exception):
    """Custom exception for analysis service errors."""

    pass
