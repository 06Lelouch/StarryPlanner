"""
Input validation BEFORE sending to GPT.

Checks:
- Input length (max 500 chars)
- Rate limiting (15 requests per minute)
- Basic sanitization (control chars, whitespace)
"""

import re
import time
from .exceptions import InputTooLongError, RateLimitExceededError


class InputLimits:
    """Configurable limits for input validation."""
    MAX_INPUT_LENGTH = 500
    RATE_LIMIT_REQUESTS = 15
    RATE_LIMIT_WINDOW_SECONDS = 60


class InputValidator:
    """
    Validates user input BEFORE sending to GPT.
    Prevents abuse and saves API costs.
    """

    def __init__(self):
        # In-memory rate limiting (resets on app restart)
        # For production: consider file-based or database storage
        self._request_timestamps: list[float] = []

    def validate_and_sanitize(self, user_input: str) -> str:
        """
        Full input validation pipeline.

        Args:
            user_input: Raw user input string

        Returns:
            Sanitized input string

        Raises:
            InputTooLongError: If input exceeds max length
            RateLimitExceededError: If rate limit exceeded
        """
        # Step 1: Sanitize
        sanitized = self._sanitize(user_input)

        # Step 2: Check length
        self._check_length(sanitized)

        # Step 3: Check rate limit
        self._check_rate_limit()

        return sanitized

    def _sanitize(self, text: str) -> str:
        """Remove control characters and normalize whitespace."""
        if text is None:
            return ""

        # Strip leading/trailing whitespace
        text = text.strip()

        # Remove null bytes and control characters (keep newlines/tabs for now)
        text = re.sub(r'[\x00-\x08\x0b\x0c\x0e-\x1f\x7f]', '', text)

        # Normalize multiple spaces/newlines to single space
        text = re.sub(r'\s+', ' ', text)

        return text

    def _check_length(self, text: str) -> None:
        """Enforce maximum input length."""
        if len(text) > InputLimits.MAX_INPUT_LENGTH:
            raise InputTooLongError(
                f"Input is {len(text)} characters",
                user_message=f"Please keep your request under {InputLimits.MAX_INPUT_LENGTH} characters."
            )

    def _check_rate_limit(self) -> None:
        """Simple sliding-window rate limiting."""
        now = time.time()
        window_start = now - InputLimits.RATE_LIMIT_WINDOW_SECONDS

        # Remove timestamps outside the window
        self._request_timestamps = [
            ts for ts in self._request_timestamps if ts > window_start
        ]

        # Check if over limit
        if len(self._request_timestamps) >= InputLimits.RATE_LIMIT_REQUESTS:
            oldest_in_window = self._request_timestamps[0]
            wait_seconds = int(oldest_in_window - window_start) + 1
            raise RateLimitExceededError(
                f"Rate limit: {len(self._request_timestamps)} requests in {InputLimits.RATE_LIMIT_WINDOW_SECONDS}s",
                user_message=f"Too many requests. Please wait {wait_seconds} seconds."
            )

        # Record this request
        self._request_timestamps.append(now)


# Singleton instance
_input_validator = None


def get_input_validator() -> InputValidator:
    """Get or create the singleton InputValidator."""
    global _input_validator
    if _input_validator is None:
        _input_validator = InputValidator()
    return _input_validator
