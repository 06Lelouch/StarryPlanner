"""
Validation module for AI Scheduler.

Provides input validation (pre-GPT) and event validation (post-GPT)
to prevent abuse and ensure data quality.

Usage:
    from validation import (
        get_input_validator,
        get_event_validator,
        sanity_check_event,
        ValidationError,
        ValidationWarning,
    )
"""

# Exceptions and warnings
from .exceptions import (
    ValidationError,
    InputTooLongError,
    RateLimitExceededError,
    InvalidEventDataError,
    InvalidTimezoneError,
    ValidationWarning,
)

# Validators
from .input_validator import get_input_validator, InputValidator, InputLimits
from .event_validator import get_event_validator, EventValidator, EventLimits
from .sanity_check import sanity_check_event

__all__ = [
    # Exceptions
    'ValidationError',
    'InputTooLongError',
    'RateLimitExceededError',
    'InvalidEventDataError',
    'InvalidTimezoneError',
    # Warnings
    'ValidationWarning',
    # Validators
    'get_input_validator',
    'get_event_validator',
    'sanity_check_event',
    'InputValidator',
    'EventValidator',
    # Limits (for reference/testing)
    'InputLimits',
    'EventLimits',
]
