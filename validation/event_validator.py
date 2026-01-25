"""
Event validation AFTER GPT extraction, and before calendar API. Make sure model gives correct format and meaningful data


Hard checks (raise exceptions):
- Required fields present
- Date/time format valid
- Timezone valid

Soft checks (return warnings):
- Title too long
- Event too far in future
- Event duration too long
"""

import re
from datetime import datetime, timedelta
from typing import Tuple, List
import pytz

from .exceptions import (
    InvalidEventDataError,
    InvalidTimezoneError,
    ValidationWarning,
)


class EventLimits:
    """Configurable limits for event validation."""
    MAX_TITLE_LENGTH = 100
    MAX_FUTURE_DAYS = 365 * 2  # 2 years
    MAX_DURATION_DAYS = 7


class EventValidator:
    """
    Validates event data from GPT extraction.

    Hard checks raise exceptions (user must fix).
    Soft checks return warnings (user can proceed anyway).
    """

    def validate_event(self, slots: dict) -> Tuple[dict, List[ValidationWarning]]:
        """
        Validate GPT-extracted event slots.

        Args:
            slots: Dict with title, date, start, end, tz, location?, notes?

        Returns:
            Tuple of (validated_slots, list_of_warnings)

        Raises:
            InvalidEventDataError: Missing/invalid required fields
            InvalidTimezoneError: Invalid IANA timezone
        """
        warnings = []

        # === HARD CHECKS (raise on failure) ===
        self._check_required_fields(slots)
        self._check_date_format(slots['date'])
        self._check_time_format(slots['start'], 'start')
        self._check_time_format(slots['end'], 'end')
        self._check_timezone(slots['tz'])

        # === SOFT CHECKS (add warnings) ===
        title_warning = self._check_title_length(slots['title'])
        if title_warning:
            warnings.append(title_warning)

        return slots, warnings

    def check_time_constraints(
        self,
        start_dt: datetime,
        end_dt: datetime
    ) -> List[ValidationWarning]:
        """
        Check time-based constraints after datetime parsing.
        Note: end < start is auto-fixed in logic, not checked here.

        Returns:
            List of warnings (may be empty)
        """
        warnings = []
        now = datetime.now(start_dt.tzinfo)

        # Check if too far in future
        max_future = now + timedelta(days=EventLimits.MAX_FUTURE_DAYS)
        if start_dt > max_future:
            years = EventLimits.MAX_FUTURE_DAYS // 365
            warnings.append(ValidationWarning(
                f"Event is more than {years} years in the future"
            ))

        # Check duration
        duration = end_dt - start_dt
        if duration > timedelta(days=EventLimits.MAX_DURATION_DAYS):
            warnings.append(ValidationWarning(
                f"Event duration is {duration.days} days"
            ))

        return warnings

    # === HARD CHECK METHODS ===

    def _check_required_fields(self, slots: dict) -> None:
        """Ensure all required fields are present and non-empty."""
        required = ['title', 'date', 'start', 'end', 'tz']
        missing = [f for f in required if not slots.get(f)]

        if missing:
            raise InvalidEventDataError(
                f"Missing fields: {', '.join(missing)}",
                user_message="I couldn't understand all the details. Please include the event title, date, and times."
            )

    def _check_date_format(self, date_str: str) -> None:
        """Validate YYYY-MM-DD format."""
        if not re.match(r'^\d{4}-\d{2}-\d{2}$', date_str):
            raise InvalidEventDataError(
                f"Invalid date format: {date_str}",
                user_message="I couldn't understand the date. Please try again with a clearer date."
            )

        # Also check it's a valid date
        try:
            datetime.strptime(date_str, '%Y-%m-%d')
        except ValueError:
            raise InvalidEventDataError(
                f"Invalid date: {date_str}",
                user_message="That date doesn't exist. Please check the date and try again."
            )

    def _check_time_format(self, time_str: str, field_name: str) -> None:
        """Validate HH:MM 24-hour format."""
        if not re.match(r'^\d{2}:\d{2}$', time_str):
            raise InvalidEventDataError(
                f"Invalid {field_name} time format: {time_str}",
                user_message=f"I couldn't understand the {field_name} time. Please try again."
            )

        # Check valid hour/minute
        try:
            hour, minute = map(int, time_str.split(':'))
            if not (0 <= hour <= 23 and 0 <= minute <= 59):
                raise ValueError()
        except ValueError:
            raise InvalidEventDataError(
                f"Invalid {field_name} time: {time_str}",
                user_message=f"The {field_name} time doesn't look right. Please use a valid time."
            )

    def _check_timezone(self, tz_str: str) -> None:
        """Validate IANA timezone string."""
        try:
            pytz.timezone(tz_str)
        except pytz.UnknownTimezoneError:
            raise InvalidTimezoneError(
                f"Unknown timezone: {tz_str}",
                user_message="Invalid timezone detected. Please try again."
            )

    # === SOFT CHECK METHODS ===

    def _check_title_length(self, title: str) -> ValidationWarning | None:
        """Warn if title exceeds recommended length."""
        if len(title) > EventLimits.MAX_TITLE_LENGTH:
            return ValidationWarning(
                f"Title is {len(title)} characters (recommended max: {EventLimits.MAX_TITLE_LENGTH})"
            )
        return None


# Singleton instance
_event_validator = None


def get_event_validator() -> EventValidator:
    """Get or create the singleton EventValidator."""
    global _event_validator
    if _event_validator is None:
        _event_validator = EventValidator()
    return _event_validator
