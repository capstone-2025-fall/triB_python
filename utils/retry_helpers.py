"""
Retry utilities for Gemini API calls with exponential backoff strategy.

PR#14: Exponential backoff 재시도 전략 구현
PR#17: InvalidGeminiResponseError 및 JSONDecodeError 재시도 추가
"""
import logging
import json
from typing import Type, Tuple
from tenacity import (
    retry,
    stop_after_attempt,
    wait_exponential,
    retry_if_exception_type,
    before_sleep_log,
    after_log,
    RetryCallState,
)
import httpx

logger = logging.getLogger(__name__)


# PR#17: Custom exception for invalid Gemini responses
class InvalidGeminiResponseError(Exception):
    """Gemini API returned invalid or malformed response."""
    pass


# Define retryable exception types for network errors
NETWORK_EXCEPTIONS: Tuple[Type[Exception], ...] = (
    httpx.TimeoutException,
    httpx.ConnectError,
    httpx.ReadError,
    httpx.WriteError,
)

# PR#17: Define retryable exception types for Gemini response errors
GEMINI_RESPONSE_EXCEPTIONS: Tuple[Type[Exception], ...] = (
    InvalidGeminiResponseError,
    json.JSONDecodeError,
)


def is_retryable_error(retry_state: RetryCallState) -> bool:
    """
    Check if an exception should be retried.

    Retryable:
    - 5xx errors (server errors)
    - 429 (rate limiting)
    - Network errors (timeout, connection, etc.)
    - PR#17: Invalid Gemini responses (InvalidGeminiResponseError)
    - PR#17: JSON parsing errors (JSONDecodeError)

    Non-retryable:
    - 4xx errors (client errors, except 429)
    """
    if retry_state.outcome is None:
        return False

    exception = retry_state.outcome.exception()
    if exception is None:
        return False

    # Check for network errors
    if isinstance(exception, NETWORK_EXCEPTIONS):
        return True

    # PR#17: Check for Gemini response errors (invalid response or JSON parse errors)
    if isinstance(exception, GEMINI_RESPONSE_EXCEPTIONS):
        logger.warning(f"Retrying due to Gemini response error: {type(exception).__name__}")
        return True

    # Check for HTTP status errors
    if isinstance(exception, httpx.HTTPStatusError):
        status_code = exception.response.status_code
        # Retry on 5xx or 429
        return status_code >= 500 or status_code == 429

    return False


# Retry decorator for Gemini content generation (long-running operations)
gemini_generate_retry = retry(
    wait=wait_exponential(multiplier=1, min=2, max=60),  # 2s -> 4s -> 8s -> 16s -> 32s -> 60s
    stop=stop_after_attempt(5),  # Max 5 attempts
    retry=is_retryable_error,
    before_sleep=before_sleep_log(logger, logging.WARNING),
    after=after_log(logger, logging.INFO),
    reraise=True,
)


# Retry decorator for embeddings (lighter operations)
gemini_embed_retry = retry(
    wait=wait_exponential(multiplier=1, min=1, max=30),  # 1s -> 2s -> 4s -> 8s -> 16s -> 30s
    stop=stop_after_attempt(3),  # Max 3 attempts
    retry=is_retryable_error,
    before_sleep=before_sleep_log(logger, logging.WARNING),
    after=after_log(logger, logging.INFO),
    reraise=True,
)


# Retry decorator for validation (medium operations)
gemini_validate_retry = retry(
    wait=wait_exponential(multiplier=1, min=2, max=45),  # 2s -> 4s -> 8s -> 16s -> 32s -> 45s
    stop=stop_after_attempt(3),  # Max 3 attempts
    retry=is_retryable_error,
    before_sleep=before_sleep_log(logger, logging.WARNING),
    after=after_log(logger, logging.INFO),
    reraise=True,
)
