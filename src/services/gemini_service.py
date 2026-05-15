"""
Gemini AI integration service for conversational document processing.
Uses Google's Generative AI to provide document assistance.
"""

import logging
import json
from typing import Optional
import google.generativeai as genai
from google.generativeai.types import GenerationConfig

from ..config import config

logger = logging.getLogger(__name__)


class GeminiService:
    """Service for interacting with Google Gemini AI API."""

    # Operations that can use the cheaper Flash model
    FLASH_OPERATIONS = {"summarize", "grammar", "format", "translate"}

    def __init__(self):
        genai.configure(api_key=config.GEMINI_API_KEY)
        self.model_name = config.GEMINI_MODEL
        self.model_name_flash = config.GEMINI_MODEL_FLASH
        
        # Generation configuration
        self.generation_config = GenerationConfig(
            temperature=0.7,
            top_p=0.95,
            top_k=40,
            max_output_tokens=8192, # Increased for larger documents
        )

    def _get_model_name_for_operation(self, operation: str) -> str:
        """Select model based on operation type."""
        if operation in self.FLASH_OPERATIONS:
            return self.model_name_flash
        return self.model_name

    async def chat(
        self,
        user_message: str,
        language: str = "en",
        file_content: Optional[str] = None,
        file_name: Optional[str] = None,
        file_type: Optional[str] = None,
        conversation_history: Optional[list[dict]] = None,
    ) -> str:
        """Have a conversational response about documents."""
        system_prompt = self._build_conversational_prompt(language, file_type)
        
        model = genai.GenerativeModel(
            model_name=self.model_name,
            system_instruction=system_prompt,
        )

        chat_session = model.start_chat(
            history=self._format_history(conversation_history)
        )

        try:
            prompt = self._build_prompt(user_message, file_content, file_name)
            response = await chat_session.send_message_async(
                prompt,
                generation_config=self.generation_config
            )
            return response.text

        except Exception as e:
            logger.error(f"Gemini API error: {e}")
            raise GeminiServiceError(f"API error: {str(e)}")

    async def process_file_request(
        self,
        user_message: str,
        file_content: Optional[str] = None,
        file_name: Optional[str] = None,
        conversation_history: Optional[list[dict]] = None,
        use_model: Optional[str] = None,
    ) -> str:
        """Process a user request related to file operations."""
        system_prompt = self._build_system_prompt()
        
        model = genai.GenerativeModel(
            model_name=use_model or self.model_name,
            system_instruction=system_prompt,
        )

        chat_session = model.start_chat(
            history=self._format_history(conversation_history)
        )

        try:
            prompt = self._build_prompt(user_message, file_content, file_name)
            response = await chat_session.send_message_async(
                prompt,
                generation_config=self.generation_config
            )
            return response.text

        except Exception as e:
            logger.error(f"Gemini API error: {e}")
            raise GeminiServiceError(f"API error: {str(e)}")

    async def analyze_for_todos(
        self,
        prompt: str,
        max_todos: int = 5,
    ) -> str:
        """Analyze document and generate todo suggestions."""
        system_prompt = f"""You are a document analysis assistant. 
Your task is to analyze documents and provide specific, actionable improvement suggestions.

Guidelines:
- Provide exactly up to {max_todos} suggestions
- Each suggestion must be specific and actionable
- Include both English and Indonesian descriptions
- Prioritize suggestions by impact (1=highest priority, 5=lowest)
- Focus on real issues, not generic advice
- Return valid JSON format only

Response format must be valid JSON with this structure:
{{
    "todos": [
        {{
            "description_en": "English description",
            "description_id": "Indonesian description",
            "action_type": "fix|edit|add|remove|format|improve",
            "target": "specific location in document",
            "suggestion": "the actual content or fix to apply",
            "priority": 1
        }}
    ]
}}"""

        model = genai.GenerativeModel(
            model_name=self.model_name,
            system_instruction=system_prompt,
        )

        try:
            response = await model.generate_content_async(
                prompt,
                generation_config=GenerationConfig(
                    response_mime_type="application/json",
                )
            )
            return response.text

        except Exception as e:
            logger.error(f"Gemini API error during analysis: {e}")
            raise GeminiServiceError(f"API error: {str(e)}")

    async def create_document(
        self,
        description: str,
        file_type: str,
        language: str = "en",
        template_content: Optional[str] = None,
    ) -> str:
        """Create document content based on user description."""
        type_instructions = {
            "docx": "Create a well-structured Word document with clear paragraphs and headings where appropriate.",
            "pdf": "Create content suitable for a PDF document with clear structure.",
            "txt": "Create plain text content with clear organization.",
            "xlsx": "Create spreadsheet data in tab-separated format. Use === Sheet: SheetName === to separate sheets.",
            "pptx": "Create presentation content. Use --- Slide N: Title --- to separate slides. Include clear bullet points.",
        }

        instruction = type_instructions.get(file_type, "Create well-organized content.")
        template_str = f"Starting template:\n{template_content}" if template_content else ""

        prompt = f"""Create a {file_type.upper()} document based on this request:

Request: {description}

{instruction}

{template_str}

Language preference: {"Indonesian" if language == "id" else "English"}

Wrap your document content with [DOCUMENT_START] and [DOCUMENT_END] markers.
Only include the document content itself, no explanations before or after the markers."""

        model = genai.GenerativeModel(
            model_name=self.model_name,
            system_instruction=self._build_system_prompt(),
        )

        try:
            response = await model.generate_content_async(
                prompt,
                generation_config=self.generation_config
            )
            return response.text

        except Exception as e:
            logger.error(f"Gemini API error during creation: {e}")
            raise GeminiServiceError(f"API error: {str(e)}")

    async def edit_document(
        self,
        instruction: str,
        content: str,
        file_type: str,
        language: str = "en",
        operation: str = "custom",
    ) -> str:
        """Edit document based on instruction."""
        prompt = f"""Edit this {file_type.upper()} document according to the instruction.

Instruction: {instruction}

Current content:
---
{content}
---

Apply the requested changes and return the complete modified document.
Wrap the edited content with [DOCUMENT_START] and [DOCUMENT_END] markers.
{"Respond in Indonesian if appropriate." if language == "id" else ""}"""

        model_name = self._get_model_name_for_operation(operation)
        return await self.process_file_request(prompt, use_model=model_name)

    async def translate_document(
        self,
        content: str,
        target_language: str,
        file_type: str,
    ) -> str:
        """Translate document to target language."""
        language_names = {
            "en": "English",
            "id": "Indonesian",
            "es": "Spanish",
            "zh": "Chinese",
            "ja": "Japanese",
            "ko": "Korean",
        }

        target = language_names.get(target_language, target_language)

        prompt = f"""Translate this {file_type.upper()} document to {target}.

Content to translate:
---
{content}
---

Translate all text content to {target} while preserving:
- Document structure and formatting
- Any technical terms that should remain in English
- Proper names

Wrap the translated content with [DOCUMENT_START] and [DOCUMENT_END] markers."""

        return await self.process_file_request(prompt, use_model=self.model_name_flash)

    async def summarize_document(
        self,
        content: str,
        file_type: str,
        language: str = "en",
    ) -> str:
        """Summarize document content."""
        lang_instruction = (
            "Respond in Indonesian." if language == "id" else "Respond in English."
        )

        prompt = f"""Summarize this {file_type.upper()} document.

Content:
---
{content}
---

Provide:
1. A brief summary (2-3 sentences)
2. Key points (bullet list)
3. Any notable observations

{lang_instruction}

If the user wants this as a new document, wrap it with [DOCUMENT_START] and [DOCUMENT_END] markers."""

        return await self.process_file_request(prompt, use_model=self.model_name_flash)

    def _build_conversational_prompt(
        self, language: str = "en", file_type: Optional[str] = None
    ) -> str:
        """Build system prompt for conversational mode."""
        lang_instruction = (
            "Respond primarily in Indonesian, but you can use English for technical terms."
            if language == "id"
            else "Respond in English."
        )

        file_context = ""
        if file_type:
            file_context = (
                f"\nThe user is currently working with a {file_type.upper()} document."
            )

        return f"""You are a helpful document assistant in a Telegram bot. You help users create and edit documents through natural conversation.

Your capabilities:
1. Create documents: Word (DOCX), PDF, Excel (XLSX), PowerPoint (PPTX), and plain text
2. Edit and improve existing documents
3. Answer questions about document content
4. Provide suggestions for improvements
5. Help with formatting and structure
{file_context}

CRITICAL REQUIREMENT - Structural Markers:
The document content contains markers like "<<< TABLE_N >>>" or "<<< IMAGE_N >>>".
- These represent complex elements (tables/images) from the original file.
- YOU MUST PRESERVE THESE MARKERS EXACTLY in your response.
- Do not modify, delete, or translate the markers (e.g., keep "<<< TABLE_0 >>>" as is).
- Place them in the appropriate position in the edited document.
- If you rewrite a section, ensure the markers that were in that section are still there.
- The text following a table marker is the current content of that table for your context only.

Guidelines:
- Be conversational and friendly, but professional
- Ask clarifying questions when the request is unclear
- Provide helpful suggestions proactively
- Keep responses concise - this is a chat interface
- When creating/editing document content, wrap it with [DOCUMENT_START] and [DOCUMENT_END]
- For Excel data, use tab-separated values
- For PowerPoint, use "--- Slide N: Title ---" format

{lang_instruction}

When the user describes what they want to create or change, help them step by step.
If they're just chatting or asking questions, respond naturally without document markers."""

    def _build_system_prompt(self) -> str:
        """Build the system prompt for document operations."""
        return """You are a document assistant specialized in creating and editing documents.

Your role is to help users with:
1. Creating new documents (Word, PDF, Excel, PowerPoint, Text)
2. Editing existing documents (summarize, rewrite, format, translate, etc.)
3. Understanding document content

CRITICAL REQUIREMENT - Structural Markers:
The document content contains markers like "<<< TABLE_N >>>" or "<<< IMAGE_N >>>".
- These represent complex elements (tables/images) from the original file.
- YOU MUST PRESERVE THESE MARKERS EXACTLY in your output.
- Do not modify, delete, or translate the markers.
- Place them in the appropriate position in the edited document.
- You can change the text around them, but keep the markers intact.

Document Format Guidelines:

For Word/PDF/Text documents:
- Use clear paragraphs separated by blank lines
- Use appropriate headings and structure

For Excel (XLSX):
- Use tab-separated values for cells
- Use "=== Sheet: SheetName ===" to separate multiple sheets
- Each row on a new line

For PowerPoint (PPTX):
- Use "--- Slide N: Title ---" to separate slides
- Use bullet points (- or *) for content
- Keep slide content concise

When providing document content that should be saved, wrap it with:
[DOCUMENT_START]
(content here)
[DOCUMENT_END]

This allows the system to extract and save the content properly.
Always provide complete document content, not partial updates."""

    def _format_history(self, history: Optional[list[dict]]) -> list[dict]:
        """Format history for Gemini API."""
        if not history:
            return []
        
        formatted = []
        for msg in history:
            role = "user" if msg["role"] == "user" else "model"
            formatted.append({"role": role, "parts": [msg["content"]]})
        return formatted

    def _build_prompt(
        self,
        user_message: str,
        file_content: Optional[str],
        file_name: Optional[str],
    ) -> str:
        """Build the prompt string."""
        if file_content and file_name:
            content_preview = file_content
            if len(file_content) > 15000: # Increased for Gemini
                content_preview = file_content[:15000] + "\n\n[Content truncated...]"

            return f"""Working with file: "{file_name}"

Content:
---
{content_preview}
---

User request: {user_message}"""
        
        return user_message

    def extract_document_content(self, response: str) -> Optional[str]:
        """Extract document content from response if present."""
        start_marker = "[DOCUMENT_START]"
        end_marker = "[DOCUMENT_END]"

        start_idx = response.find(start_marker)
        end_idx = response.find(end_marker)

        if start_idx != -1 and end_idx != -1 and start_idx < end_idx:
            content = response[start_idx + len(start_marker) : end_idx].strip()
            return content

        return None

    def has_document_content(self, response: str) -> bool:
        """Check if response contains document content markers."""
        return "[DOCUMENT_START]" in response and "[DOCUMENT_END]" in response


class GeminiServiceError(Exception):
    """Custom exception for Gemini service errors."""
    pass
