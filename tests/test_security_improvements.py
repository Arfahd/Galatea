"""
Automated tests for security improvements in GalateaCloud.

Tests cover:
1. Global Rate Limiter
2. Path Validation in FileService
3. Config Defaults
4. Activity Logger PII Protection
5. Template Key Validation
6. Error Message Patterns (Static Analysis)
7. Broadcast Confirmation Logic
8. Input Validation (pagination, indices)

Run with: pytest tests/test_security_improvements.py -v
Or: python -m pytest tests/test_security_improvements.py -v
"""

import sys
import os
import time
import re
import asyncio
from pathlib import Path
from unittest.mock import patch, MagicMock, AsyncMock

import pytest


# Helper to run async tests without pytest-asyncio
def run_async(coro):
    """Run an async coroutine synchronously."""
    return asyncio.get_event_loop().run_until_complete(coro)


# Add project root to path
PROJECT_ROOT = Path(__file__).parent.parent
sys.path.insert(0, str(PROJECT_ROOT))


# =============================================================================
# Test 1: Global Rate Limiter
# =============================================================================


class TestGlobalRateLimiter:
    """Test the global rate limiter for spam protection."""

    def setup_method(self):
        """Reset rate limiter before each test."""
        # Import fresh instance
        from src.utils.global_rate_limiter import GlobalRateLimiter

        # Create a fresh instance for testing (bypass singleton)
        self.limiter = GlobalRateLimiter.__new__(GlobalRateLimiter)
        self.limiter._initialized = False
        self.limiter.__init__()

    def test_allows_normal_requests(self):
        """Normal rate requests should pass through."""
        user_id = 12345

        # First few requests should be allowed (with delays to avoid burst limit)
        for i in range(5):
            assert self.limiter.check_rate_limit(user_id) is True, (
                f"Request {i + 1} should be allowed"
            )
            time.sleep(0.35)  # 350ms delay to avoid burst limit (max 3/second)

    def test_blocks_burst_over_3_per_second(self):
        """More than 3 requests per second should be blocked."""
        user_id = 12346

        # Make 3 requests quickly (should all pass)
        for i in range(3):
            assert self.limiter.check_rate_limit(user_id) is True, (
                f"Request {i + 1} should pass"
            )

        # 4th request within same second should be blocked
        assert self.limiter.check_rate_limit(user_id) is False, (
            "4th request in 1 second should be blocked"
        )

    def test_allows_requests_after_burst_cooldown(self):
        """After waiting 1 second, burst should reset."""
        user_id = 12347

        # Hit burst limit
        for _ in range(3):
            self.limiter.check_rate_limit(user_id)

        # Wait for burst window to pass
        time.sleep(1.1)

        # Should be allowed again
        assert self.limiter.check_rate_limit(user_id) is True, (
            "Request after cooldown should pass"
        )

    def test_blocks_over_30_per_minute(self):
        """More than 30 requests per minute should be blocked."""
        user_id = 12348

        # Make 30 requests with delays to avoid burst limit (3/second = 334ms minimum)
        for i in range(30):
            result = self.limiter.check_rate_limit(user_id)
            assert result is True, f"Request {i + 1} should pass"
            time.sleep(0.35)  # 350ms between requests to stay under burst limit

        # 31st request should be blocked
        assert self.limiter.check_rate_limit(user_id) is False, (
            "31st request should be blocked"
        )

    def test_different_users_independent(self):
        """Rate limits should be independent per user."""
        user_a = 11111
        user_b = 22222

        # Hit burst limit for user A
        for _ in range(3):
            self.limiter.check_rate_limit(user_a)

        # User B should still be allowed
        assert self.limiter.check_rate_limit(user_b) is True, (
            "User B should not be affected by User A"
        )

    def test_cleanup_removes_stale_entries(self):
        """Cleanup should remove old entries."""
        user_id = 12349

        # Add some requests
        self.limiter.check_rate_limit(user_id)

        # Manually age the entries
        old_time = time.time() - 400  # 6+ minutes ago
        self.limiter._requests[user_id] = [old_time]

        # Run cleanup
        removed = self.limiter.cleanup()

        assert removed >= 1, "Should remove stale entry"
        assert user_id not in self.limiter._requests, "Stale user should be removed"

    def test_get_stats_returns_correct_format(self):
        """Stats should return expected structure."""
        stats = self.limiter.get_stats()

        assert "tracked_users" in stats
        assert "active_users" in stats
        assert "max_per_minute" in stats
        assert "max_per_second" in stats
        assert stats["max_per_minute"] == 30
        assert stats["max_per_second"] == 3

    def test_get_user_request_count(self):
        """Should return correct count of recent requests."""
        user_id = 12350

        # Make 5 requests with delays to avoid burst limit
        for _ in range(5):
            self.limiter.check_rate_limit(user_id)
            time.sleep(0.35)  # 350ms delay

        count = self.limiter.get_user_request_count(user_id)
        assert count == 5, f"Expected 5 requests, got {count}"


# =============================================================================
# Test 2: Path Validation in FileService
# =============================================================================


class TestPathValidation:
    """Test path validation in FileService.get_user_directory()."""

    def test_valid_positive_user_id(self):
        """Valid positive user IDs should work."""
        from src.services.file_service import FileService

        with patch.object(Path, "mkdir"):
            fs = FileService()
            # Should not raise
            path = fs.get_user_directory(123456)
            assert "123456" in str(path)

    def test_rejects_zero_user_id(self):
        """User ID 0 should be rejected."""
        from src.services.file_service import FileService, FileServiceError

        fs = FileService()

        with pytest.raises(FileServiceError) as exc_info:
            fs.get_user_directory(0)

        assert "Invalid user ID" in str(exc_info.value)

    def test_rejects_negative_user_id(self):
        """Negative user IDs should be rejected."""
        from src.services.file_service import FileService, FileServiceError

        fs = FileService()

        with pytest.raises(FileServiceError) as exc_info:
            fs.get_user_directory(-1)

        assert "Invalid user ID" in str(exc_info.value)

    def test_rejects_non_integer_user_id(self):
        """Non-integer user IDs should be rejected."""
        from src.services.file_service import FileService, FileServiceError

        fs = FileService()

        # String should fail
        with pytest.raises(FileServiceError):
            fs.get_user_directory("12345")  # type: ignore

        # Float should fail
        with pytest.raises(FileServiceError):
            fs.get_user_directory(123.45)  # type: ignore

    def test_path_under_user_files_dir(self):
        """Generated path should be under USER_FILES_DIR."""
        from src.services.file_service import FileService
        from src.config import config

        with patch.object(Path, "mkdir"):
            fs = FileService()
            path = fs.get_user_directory(999999)

            # Verify path is under USER_FILES_DIR
            assert (
                str(config.USER_FILES_DIR) in str(path.parent)
                or path.parent == config.USER_FILES_DIR
            )


# =============================================================================
# Test 3: Config Defaults
# =============================================================================


class TestConfigDefaults:
    """Test configuration default values."""

    def test_monthly_limit_is_100(self):
        """Default monthly limit should be 100 (matching .env.example)."""
        # Clear any cached env var
        with patch.dict(os.environ, {}, clear=False):
            # Remove MONTHLY_REQUEST_LIMIT if set
            os.environ.pop("MONTHLY_REQUEST_LIMIT", None)

            # Re-import to get fresh defaults
            import importlib
            from src import config as config_module

            importlib.reload(config_module)

            # Check default is 100
            assert config_module.config.MONTHLY_REQUEST_LIMIT == 100

    def test_supported_languages_exist(self):
        """Should have at least en and id languages."""
        from src.config import config

        assert "en" in config.SUPPORTED_LANGUAGES
        assert "id" in config.SUPPORTED_LANGUAGES


# =============================================================================
# Test 4: Activity Logger PII Protection
# =============================================================================


class TestActivityLoggerPII:
    """Test that activity logger doesn't log sensitive message content (static analysis)."""

    def get_activity_logger_content(self) -> str:
        """Read activity_logger.py content."""
        filepath = PROJECT_ROOT / "activity_logger.py"
        with open(filepath, "r") as f:
            return f.read()

    def test_log_ai_chat_only_logs_length(self):
        """log_ai_chat should log message length, not content."""
        content = self.get_activity_logger_content()

        # Find the log_ai_chat function
        func_start = content.find("async def log_ai_chat")
        if func_start == -1:
            pytest.fail("Could not find log_ai_chat function")

        # Get the function body (until next function or end)
        func_end = content.find("\nasync def ", func_start + 1)
        if func_end == -1:
            func_end = len(content)
        func_content = content[func_start:func_end]

        # Should log only length
        assert "len=" in func_content or "len(" in func_content, (
            "log_ai_chat should include message length"
        )

        # Should NOT have message content directly in log
        # The old pattern was: message[:25] + "..." which would leak content
        assert "message[:25]" not in func_content, (
            "Should not log first 25 chars of message"
        )
        assert "preview = message" not in func_content, (
            "Should not create preview from message content"
        )

    def test_message_content_not_truncated_logged(self):
        """Message should not be truncated and logged (old pattern)."""
        content = self.get_activity_logger_content()

        # Old dangerous patterns that leaked message content
        dangerous_patterns = [
            "message[:",  # Truncating message
            "message[0:",  # Truncating message
            '+ "..."',  # Adding ellipsis (truncation indicator)
            "preview = message",  # Creating preview variable
        ]

        # Find log_ai_chat function
        func_start = content.find("async def log_ai_chat")
        func_end = content.find("\nasync def ", func_start + 1)
        if func_end == -1:
            func_end = len(content)
        func_content = content[func_start:func_end]

        for pattern in dangerous_patterns:
            assert pattern not in func_content, (
                f"Found dangerous pattern '{pattern}' that could leak message content"
            )

    def test_log_format_is_length_only(self):
        """Log call should use len=N format."""
        content = self.get_activity_logger_content()

        # Find log_ai_chat function
        func_start = content.find("async def log_ai_chat")
        func_end = content.find("\nasync def ", func_start + 1)
        if func_end == -1:
            func_end = len(content)
        func_content = content[func_start:func_end]

        # Should have format like f"len={len(message)}"
        assert (
            'f"len={len(message)}"' in func_content
            or "f'len={len(message)}'" in func_content
        ), "Should log message length in format 'len=N'"


# =============================================================================
# Test 5: Template Key Validation
# =============================================================================


class TestTemplateValidation:
    """Test template key validation logic."""

    def test_blank_template_valid(self):
        """'blank' should be a valid template key."""
        from src.templates import PPTX_TEMPLATES

        # 'blank' is special-cased or should be in PPTX_TEMPLATES
        assert "blank" in PPTX_TEMPLATES

    def test_known_templates_valid(self):
        """All known template keys should be in PPTX_TEMPLATES."""
        from src.templates import PPTX_TEMPLATES

        expected_templates = [
            "blank",
            "business_proposal",
            "project_status",
            "meeting_agenda",
            "training",
            "product_pitch",
        ]

        for template_key in expected_templates:
            assert template_key in PPTX_TEMPLATES, (
                f"Template '{template_key}' should exist"
            )

    def test_unknown_template_invalid(self):
        """Unknown template keys should not be in PPTX_TEMPLATES."""
        from src.templates import PPTX_TEMPLATES

        invalid_keys = [
            "nonexistent",
            "../../etc/passwd",
            "<script>alert(1)</script>",
            "'; DROP TABLE templates;--",
        ]

        for key in invalid_keys:
            assert key not in PPTX_TEMPLATES, f"Key '{key}' should not be valid"

    def test_empty_string_invalid(self):
        """Empty string should not be a valid template."""
        from src.templates import PPTX_TEMPLATES

        assert "" not in PPTX_TEMPLATES


# =============================================================================
# Test 6: Error Message Patterns (Static Analysis)
# =============================================================================


class TestErrorMessagePatterns:
    """Static analysis of error handling in handler files."""

    def get_handler_content(self, filename: str) -> str:
        """Read handler file content."""
        filepath = PROJECT_ROOT / "src" / "handlers" / filename
        with open(filepath, "r") as f:
            return f.read()

    def test_no_error_str_e_in_bot_handlers(self):
        """bot_handlers.py should not expose exception details to users."""
        content = self.get_handler_content("bot_handlers.py")

        # Should not have error=str(e) pattern
        dangerous_patterns = [
            r"error=str\(e\)",
            r"error_processing.*error=",
            r"error_file_read.*error=",
            r"error_file_write.*error=",
        ]

        for pattern in dangerous_patterns:
            matches = re.findall(pattern, content)
            assert len(matches) == 0, f"Found dangerous pattern '{pattern}': {matches}"

    def test_no_error_str_e_in_callback_handlers(self):
        """callback_handlers.py should not expose exception details to users."""
        content = self.get_handler_content("callback_handlers.py")

        dangerous_patterns = [
            r"error=str\(e\)",
            r"error_processing.*error=",
        ]

        for pattern in dangerous_patterns:
            matches = re.findall(pattern, content)
            assert len(matches) == 0, f"Found dangerous pattern '{pattern}': {matches}"

    def test_exceptions_use_exc_info_true(self):
        """Exception logging should include exc_info=True for stack traces."""
        content = self.get_handler_content("bot_handlers.py")

        # Find all logger.error calls with exception info
        # Should have exc_info=True for proper debugging
        error_calls_with_exc_info = re.findall(
            r"logger\.error\([^)]+exc_info=True", content
        )

        # Should have at least a few (we added 5+ in bot_handlers)
        assert len(error_calls_with_exc_info) >= 4, (
            f"Expected at least 4 logger.error calls with exc_info=True, found {len(error_calls_with_exc_info)}"
        )

    def test_error_general_uses_lang_variable(self):
        """error_general messages should use 'lang' not hardcoded 'en'."""
        content = self.get_handler_content("bot_handlers.py")

        # Find error_general calls
        error_general_calls = re.findall(
            r'get_message\(["\']error_general["\'],\s*(\w+)', content
        )

        # Most should use 'lang' variable, not "en"
        lang_uses = [call for call in error_general_calls if call == "lang"]
        en_uses = [
            call for call in error_general_calls if call == '"en"' or call == "'en'"
        ]

        # Allow some "en" for global error handler, but most should be lang
        assert len(lang_uses) >= len(en_uses), (
            f"Most error_general calls should use 'lang', found {len(lang_uses)} lang vs {len(en_uses)} 'en'"
        )


# =============================================================================
# Test 7: Broadcast Confirmation Logic
# =============================================================================


class TestBroadcastConfirmation:
    """Test broadcast command confirmation logic."""

    def test_broadcast_code_has_confirmation_check(self):
        """broadcast_command should check for pending confirmation."""
        content = Path(
            PROJECT_ROOT / "src" / "handlers" / "bot_handlers.py"
        ).read_text()

        # Should have pending_broadcast check
        assert "pending_broadcast" in content, "Should have pending_broadcast variable"
        assert (
            "context.user_data.get" in content
            or 'context.user_data["pending_broadcast"]' in content
        ), "Should check user_data for pending broadcast"

    def test_broadcast_requires_same_message_twice(self):
        """Broadcast should require same message twice to confirm."""
        content = Path(
            PROJECT_ROOT / "src" / "handlers" / "bot_handlers.py"
        ).read_text()

        # Find the broadcast function
        broadcast_section = content[content.find("async def broadcast_command") :]
        broadcast_section = broadcast_section[
            : broadcast_section.find("\nasync def ", 1)
        ]

        # Should compare pending with current message
        assert (
            "pending != broadcast_message" in broadcast_section
            or "pending == broadcast_message" in broadcast_section
        ), "Should compare pending with current broadcast message"

    def test_broadcast_clears_pending_on_no_args(self):
        """Broadcast with no args should clear pending."""
        content = Path(
            PROJECT_ROOT / "src" / "handlers" / "bot_handlers.py"
        ).read_text()

        # Should clear pending when no args
        assert 'context.user_data.pop("pending_broadcast"' in content, (
            "Should clear pending_broadcast when no args provided"
        )


# =============================================================================
# Test 8: Input Validation (Pagination, Indices)
# =============================================================================


class TestInputValidation:
    """Test input validation for pagination and todo indices."""

    def test_preview_page_validation_exists(self):
        """Preview page handler should validate page numbers."""
        content = Path(
            PROJECT_ROOT / "src" / "handlers" / "callback_handlers.py"
        ).read_text()

        # Find preview_page handling section
        assert "preview_page_" in content, "Should handle preview_page callbacks"

        # Should have bounds checking
        assert "page_num < 1" in content or "page_num <= 0" in content, (
            "Should check for page numbers less than 1"
        )
        assert "page_num > 10000" in content or "page_num >= 10000" in content, (
            "Should have upper bound check for page numbers"
        )

    def test_preview_page_catches_value_error(self):
        """Preview page should catch ValueError for non-numeric input."""
        content = Path(
            PROJECT_ROOT / "src" / "handlers" / "callback_handlers.py"
        ).read_text()

        # Find the preview handling section
        preview_section_start = content.find('if data.startswith("preview_page_")')
        if preview_section_start == -1:
            pytest.fail("Could not find preview_page_ handling")

        preview_section = content[preview_section_start : preview_section_start + 500]

        assert "except ValueError" in preview_section, (
            "Should catch ValueError for invalid page numbers"
        )

    def test_todo_index_validation_exists(self):
        """Todo handlers should validate indices."""
        content = Path(
            PROJECT_ROOT / "src" / "handlers" / "callback_handlers.py"
        ).read_text()

        # Should check index bounds
        assert "idx < 0" in content, "Should check for negative indices"
        assert "idx >= len(todos)" in content, "Should check index against todos length"

    def test_template_validation_exists(self):
        """Template handler should validate template keys."""
        content = Path(
            PROJECT_ROOT / "src" / "handlers" / "callback_handlers.py"
        ).read_text()

        # Should validate against PPTX_TEMPLATES
        assert (
            "template_key not in PPTX_TEMPLATES" in content
            or 'template_key != "blank" and template_key not in PPTX_TEMPLATES'
            in content
        ), "Should validate template key against PPTX_TEMPLATES"


# =============================================================================
# Test 9: Global Rate Limiter Integration
# =============================================================================


class TestGlobalRateLimiterIntegration:
    """Test that global rate limiter is properly integrated."""

    def test_callback_handlers_imports_global_rate_limiter(self):
        """callback_handlers.py should import global_rate_limiter."""
        content = Path(
            PROJECT_ROOT / "src" / "handlers" / "callback_handlers.py"
        ).read_text()

        assert (
            "from ..utils.global_rate_limiter import global_rate_limiter" in content
        ), "Should import global_rate_limiter"

    def test_callback_handlers_uses_global_rate_limiter(self):
        """callback_handlers should check global rate limit."""
        content = Path(
            PROJECT_ROOT / "src" / "handlers" / "callback_handlers.py"
        ).read_text()

        assert "global_rate_limiter.check_rate_limit" in content, (
            "Should call global_rate_limiter.check_rate_limit"
        )

    def test_rate_limit_check_before_processing(self):
        """Rate limit check should happen early in handle_callback_query."""
        content = Path(
            PROJECT_ROOT / "src" / "handlers" / "callback_handlers.py"
        ).read_text()

        # Find handle_callback_query function
        func_start = content.find("async def handle_callback_query")
        func_end = content.find("\nasync def ", func_start + 1)
        func_content = content[func_start:func_end]

        # Rate limit check should come before route handling
        rate_limit_pos = func_content.find("global_rate_limiter.check_rate_limit")
        route_pos = func_content.find('if data.startswith("action_")')

        assert rate_limit_pos < route_pos, (
            "Rate limit check should happen before routing to handlers"
        )


# =============================================================================
# Test 10: Backup Script Security
# =============================================================================


class TestBackupScriptSecurity:
    """Test backup script uses secure temp file handling."""

    def test_backup_script_uses_mktemp(self):
        """Backup script should use mktemp for temporary files."""
        script_path = PROJECT_ROOT / "scripts" / "backup.sh"
        content = script_path.read_text()

        # Should use mktemp
        assert "mktemp" in content, "Should use mktemp for secure temp file creation"

        # Should not use predictable /tmp path directly
        assert '"/tmp/galatea_verify.db"' not in content, (
            "Should not use predictable temp file path"
        )

    def test_backup_script_cleans_temp_file(self):
        """Backup script should clean up temp file."""
        script_path = PROJECT_ROOT / "scripts" / "backup.sh"
        content = script_path.read_text()

        # Should remove the temp file
        assert "rm -f" in content and "VERIFY_FILE" in content, (
            "Should clean up temp file with rm -f"
        )


# =============================================================================
# Main entry point for unittest compatibility
# =============================================================================

if __name__ == "__main__":
    # Support both pytest and unittest
    pytest.main([__file__, "-v"])
