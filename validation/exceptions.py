"""
Custom exceptions for validation errors.

Hard errors: User must fix before proceeding
Soft warnings: User can choose to proceed anyway
"""

from dataclasses import dataclass


# ============ HARD ERRORS ============
# These block the event from being created

class ValidationError(Exception):
    """Base exception for all validation errors."""
    def __init__(self, message: str, user_message: str = None):
        super().__init__(message)
        self.user_message = user_message or message


class InputTooLongError(ValidationError):
    """Input exceeds maximum allowed length."""
    pass


class RateLimitExceededError(ValidationError):
    """Too many requests in time window."""
    pass


class InvalidEventDataError(ValidationError):
    """GPT returned invalid/incomplete event data."""
    pass


class InvalidTimezoneError(ValidationError):
    """Invalid IANA timezone string."""
    pass


# ============ SOFT WARNINGS ============
# These let user decide whether to proceed

@dataclass
class ValidationWarning:
    """
    A soft warning that doesn't block the event.
    User sees "Are you sure?" and can proceed or cancel.
    """
    message: str  # Human-readable, e.g. "Event is 3 years in the future"
