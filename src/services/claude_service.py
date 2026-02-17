"""
Claude AI integration service for conversational document processing.
Enhanced for natural conversation and multi-format document support.
"""

import logging
from typing import Optional
from anthropic import AsyncAnthropic, APIError

from ..config import config

logger = logging.getLogger(__name__)


class ClaudeService:
    """Service for interacting with Claude AI API."""

    # Operations that can use the cheaper Haiku model
    HAIKU_OPERATIONS = {"summarize", "grammar", "format", "translate"}

    def __init__(self):
        self.client = AsyncAnthropic(
            api_key=config.ANTHROPIC_API_KEY,
            timeout=60.0,  # 60 second timeout for API calls
        )
        self.model = config.CLAUDE_MODEL
        self.model_haiku = config.CLAUDE_MODEL_HAIKU
        self.max_tokens = config.CLAUDE_MAX_TOKENS

    def _get_model_for_operation(self, operation: str) -> str:
        """
        Select model based on operation type.

        Simple operations (summarize, grammar, format, translate) use Haiku (cheaper).
        Complex operations (rewrite, create, analyze, chat) use Sonnet (smarter).
        """
        if operation in self.HAIKU_OPERATIONS:
            return self.model_haiku
        return self.model

    async def chat(
        self,
        user_message: str,
        language: str = "en",
        file_content: Optional[str] = None,
        file_name: Optional[str] = None,
        file_type: Optional[str] = None,
        conversation_history: Optional[list[dict]] = None,
    ) -> str:
        """
        Have a conversational response about documents.

        Args:
            user_message: User's message
            language: User's preferred language
            file_content: Current document content if any
            file_name: Current filename if any
            file_type: Current file type if any
            conversation_history: Previous conversation

        Returns:
            AI response text
        """
        system_prompt = self._build_conversational_prompt(language, file_type)
        messages = self._build_messages(
            user_message, file_content, file_name, conversation_history
        )

        try:
            response = await self.client.messages.create(
                model=self.model,
                max_tokens=self.max_tokens,
                system=system_prompt,
                messages=messages,
            )

            return response.content[0].text

        except APIError as e:
            logger.error(f"Claude API error: {e}")
            raise ClaudeServiceError(f"API error: {e.message}")
        except Exception as e:
            logger.error(f"Unexpected error calling Claude: {e}")
            raise ClaudeServiceError(f"Unexpected error: {str(e)}")

    async def process_file_request(
        self,
        user_message: str,
        file_content: Optional[str] = None,
        file_name: Optional[str] = None,
        conversation_history: Optional[list[dict]] = None,
        use_model: Optional[str] = None,
    ) -> str:
        """
        Process a user request related to file operations.

        Args:
            user_message: The user's message/instruction
            file_content: Content of the file being worked on (if any)
            file_name: Name of the file (if any)
            conversation_history: Previous messages in the conversation
            use_model: Specific model to use (defaults to Sonnet)

        Returns:
            Claude's response text
        """
        system_prompt = self._build_system_prompt()
        messages = self._build_messages(
            user_message, file_content, file_name, conversation_history
        )

        model = use_model or self.model

        try:
            response = await self.client.messages.create(
                model=model,
                max_tokens=self.max_tokens,
                system=system_prompt,
                messages=messages,
            )

            return response.content[0].text

        except APIError as e:
            logger.error(f"Claude API error: {e}")
            raise ClaudeServiceError(f"API error: {e.message}")
        except Exception as e:
            logger.error(f"Unexpected error calling Claude: {e}")
            raise ClaudeServiceError(f"Unexpected error: {str(e)}")

    async def analyze_for_todos(
        self,
        prompt: str,
        max_todos: int = 5,
    ) -> str:
        """
        Analyze document and generate todo suggestions.

        Args:
            prompt: Analysis prompt with document content
            max_todos: Maximum number of todos to generate

        Returns:
            JSON response with todos
        """
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

        try:
            response = await self.client.messages.create(
                model=self.model,
                max_tokens=self.max_tokens,
                system=system_prompt,
                messages=[{"role": "user", "content": prompt}],
            )

            return response.content[0].text

        except APIError as e:
            logger.error(f"Claude API error during analysis: {e}")
            raise ClaudeServiceError(f"API error: {e.message}")
        except Exception as e:
            logger.error(f"Unexpected error during analysis: {e}")
            raise ClaudeServiceError(f"Unexpected error: {str(e)}")

    async def create_document(
        self,
        description: str,
        file_type: str,
        language: str = "en",
        template_content: Optional[str] = None,
    ) -> str:
        """
        Create document content based on user description.

        Args:
            description: User's description of what they want
            file_type: Target document type
            language: User's language preference
            template_content: Optional template to build upon

        Returns:
            Generated document content
        """
        type_instructions = {
            "docx": "Create a well-structured Word document with clear paragraphs and headings where appropriate.",
            "pdf": "Create content suitable for a PDF document with clear structure.",
            "txt": "Create plain text content with clear organization.",
            "xlsx": "Create spreadsheet data in tab-separated format. Use === Sheet: SheetName === to separate sheets.",
            "pptx": "Create presentation content. Use --- Slide N: Title --- to separate slides. Include clear bullet points.",
        }

        instruction = type_instructions.get(file_type, "Create well-organized content.")

        prompt = f"""Create a {file_type.upper()} document based on this request:

Request: {description}

{instruction}

{"Starting template:\n" + template_content if template_content else ""}

Language preference: {"Indonesian" if language == "id" else "English"}

Wrap your document content with [DOCUMENT_START] and [DOCUMENT_END] markers.
Only include the document content itself, no explanations before or after the markers."""

        try:
            response = await self.client.messages.create(
                model=self.model,
                max_tokens=self.max_tokens,
                system=self._build_system_prompt(),
                messages=[{"role": "user", "content": prompt}],
            )

            return response.content[0].text

        except APIError as e:
            logger.error(f"Claude API error during creation: {e}")
            raise ClaudeServiceError(f"API error: {e.message}")
        except Exception as e:
            logger.error(f"Unexpected error during creation: {e}")
            raise ClaudeServiceError(f"Unexpected error: {str(e)}")

    async def edit_document(
        self,
        instruction: str,
        content: str,
        file_type: str,
        language: str = "en",
        operation: str = "custom",
    ) -> str:
        """
        Edit document based on instruction.

        Args:
            instruction: Edit instruction
            content: Current document content
            file_type: Document type
            language: User's language
            operation: Operation type for model selection (summarize, grammar, format, rewrite, custom)

        Returns:
            Response with edited content
        """
        prompt = f"""Edit this {file_type.upper()} document according to the instruction.

Instruction: {instruction}

Current content:
---
{content}
---

Apply the requested changes and return the complete modified document.
Wrap the edited content with [DOCUMENT_START] and [DOCUMENT_END] markers.
{"Respond in Indonesian if appropriate." if language == "id" else ""}"""

        # Select model based on operation type
        model = self._get_model_for_operation(operation)
        return await self.process_file_request(prompt, use_model=model)

    async def translate_document(
        self,
        content: str,
        target_language: str,
        file_type: str,
    ) -> str:
        """
        Translate document to target language.

        Args:
            content: Document content
            target_language: Target language code
            file_type: Document type

        Returns:
            Translated content
        """
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

        # Use Haiku for translation (simpler task)
        return await self.process_file_request(prompt, use_model=self.model_haiku)

    async def summarize_document(
        self,
        content: str,
        file_type: str,
        language: str = "en",
    ) -> str:
        """
        Summarize document content.

        Args:
            content: Document content
            file_type: Document type
            language: Output language

        Returns:
            Summary response
        """
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

        # Use Haiku for summarization (simpler task)
        return await self.process_file_request(prompt, use_model=self.model_haiku)

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

    def _build_messages(
        self,
        user_message: str,
        file_content: Optional[str],
        file_name: Optional[str],
        conversation_history: Optional[list[dict]],
    ) -> list[dict]:
        """Build the messages array for the API call."""
        messages = []

        # Add conversation history if present
        if conversation_history:
            messages.extend(conversation_history)

        # Build current user message
        current_message = ""

        if file_content and file_name:
            # Truncate very long content
            content_preview = file_content
            if len(file_content) > 6000:
                content_preview = file_content[:6000] + "\n\n[Content truncated...]"

            current_message = f"""Working with file: "{file_name}"

Content:
---
{content_preview}
---

User request: {user_message}"""
        else:
            current_message = user_message

        messages.append({"role": "user", "content": current_message})

        return messages

    def extract_document_content(self, response: str) -> Optional[str]:
        """
        Extract document content from Claude's response if present.

        Args:
            response: Claude's response text

        Returns:
            Extracted document content or None
        """
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


class ClaudeServiceError(Exception):
    """Custom exception for Claude service errors."""

    pass
