"""
Retry utility with exponential backoff for async operations.
Handles transient network failures gracefully.
"""

import asyncio
import logging
from functools import wraps
from typing import Tuple, Type, Callable, Any

logger = logging.getLogger(__name__)

# Default exceptions that should trigger a retry
DEFAULT_RETRYABLE_EXCEPTIONS: Tuple[Type[Exception], ...] = (
    TimeoutError,
    ConnectionError,
    OSError,
)


def retry_async(
    max_retries: int = 3,
    base_delay: float = 1.0,
    max_delay: float = 30.0,
    retryable_exceptions: Tuple[Type[Exception], ...] = DEFAULT_RETRYABLE_EXCEPTIONS,
    on_retry: Callable[[Exception, int], Any] = None,
):
    """
    Decorator for retrying async functions with exponential backoff.

    Args:
        max_retries: Maximum number of retry attempts (default: 3)
        base_delay: Initial delay between retries in seconds (default: 1.0)
        max_delay: Maximum delay between retries in seconds (default: 30.0)
        retryable_exceptions: Tuple of exceptions that trigger a retry
        on_retry: Optional callback function called before each retry
                  Receives (exception, attempt_number) as arguments

    Example:
        @retry_async(max_retries=3, base_delay=1.0)
        async def fetch_data():
            # This will retry up to 3 times on timeout/connection errors
            return await some_api_call()
    """

    def decorator(func):
        @wraps(func)
        async def wrapper(*args, **kwargs):
            last_exception = None

            for attempt in range(max_retries + 1):
                try:
                    return await func(*args, **kwargs)
                except retryable_exceptions as e:
                    last_exception = e

                    if attempt < max_retries:
                        # Calculate delay with exponential backoff
                        delay = min(base_delay * (2**attempt), max_delay)

                        logger.warning(
                            f"{func.__name__} failed (attempt {attempt + 1}/{max_retries + 1}), "
                            f"retrying in {delay:.1f}s: {type(e).__name__}: {e}"
                        )

                        # Call on_retry callback if provided
                        if on_retry:
                            try:
                                result = on_retry(e, attempt + 1)
                                if asyncio.iscoroutine(result):
                                    await result
                            except Exception as callback_error:
                                logger.error(
                                    f"on_retry callback failed: {callback_error}"
                                )

                        await asyncio.sleep(delay)
                    else:
                        logger.error(
                            f"{func.__name__} failed after {max_retries + 1} attempts: "
                            f"{type(e).__name__}: {e}"
                        )

            # Re-raise the last exception after all retries exhausted
            raise last_exception

        return wrapper

    return decorator


class RetryContext:
    """
    Context manager for retry logic when decorator isn't suitable.

    Example:
        async with RetryContext(max_retries=3) as retry:
            while retry.should_continue():
                try:
                    result = await some_operation()
                    break
                except TimeoutError as e:
                    await retry.handle_error(e)
    """

    def __init__(
        self,
        max_retries: int = 3,
        base_delay: float = 1.0,
        max_delay: float = 30.0,
        retryable_exceptions: Tuple[
            Type[Exception], ...
        ] = DEFAULT_RETRYABLE_EXCEPTIONS,
    ):
        self.max_retries = max_retries
        self.base_delay = base_delay
        self.max_delay = max_delay
        self.retryable_exceptions = retryable_exceptions
        self.attempt = 0
        self.last_exception = None

    async def __aenter__(self):
        return self

    async def __aexit__(self, exc_type, exc_val, exc_tb):
        return False

    def should_continue(self) -> bool:
        """Check if we should continue trying."""
        return self.attempt <= self.max_retries

    async def handle_error(self, exception: Exception) -> None:
        """
        Handle an error, waiting before the next retry if appropriate.

        Raises:
            The original exception if max retries exceeded or not retryable.
        """
        self.last_exception = exception

        if not isinstance(exception, self.retryable_exceptions):
            raise exception

        if self.attempt >= self.max_retries:
            raise exception

        delay = min(self.base_delay * (2**self.attempt), self.max_delay)

        logger.warning(
            f"Operation failed (attempt {self.attempt + 1}/{self.max_retries + 1}), "
            f"retrying in {delay:.1f}s: {type(exception).__name__}: {exception}"
        )

        self.attempt += 1
        await asyncio.sleep(delay)
