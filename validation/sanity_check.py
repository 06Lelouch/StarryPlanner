"""
GPT-based semantic sanity check for events.

CURRENTLY DISABLED - always returns None (valid).

When enabled, this will catch semantic nonsense like:
- Gibberish titles ("asdfghjkl meeting")
- Impossible locations
- Clearly fake events

To enable: uncomment the implementation in sanity_check_event()
"""

from .exceptions import ValidationWarning


def sanity_check_event(ev: dict) -> ValidationWarning | None:
    """
    GPT sanity check for semantic validation.

    DISABLED FOR NOW - always returns None.

    Args:
        ev: Event dict with title, date, start, end, tz, location?, notes?

    Returns:
        None if valid, ValidationWarning if suspicious
    """
    # Currently disabled - always passes
    return None

    # =========================================================
    # FUTURE IMPLEMENTATION - 
    # =========================================================
    #
    # import json
    # from openai import OpenAI
    # import os
    #
    # client = OpenAI(api_key=os.getenv("OPENAI_API_KEY"))
    #
    # prompt = f"""Check if this calendar event makes sense:
    # Title: {ev['title']}
    # Date: {ev['date']} {ev['start']}-{ev['end']}
    # Location: {ev.get('location', 'N/A')}
    # Notes: {ev.get('notes', 'N/A')}
    #
    # Reply with JSON only: {{"valid": true, "issue": null}} or {{"valid": false, "issue": "brief description"}}
    #
    # Flag issues like:
    # - Nonsense/gibberish titles
    # - Impossible or clearly fake locations
    # - Contradictory information
    # - Clearly joke/test events"""
    #
    # try:
    #     resp = client.chat.completions.create(
    #         model="gpt-4o-mini",
    #         messages=[{"role": "user", "content": prompt}],
    #         max_tokens=50,  # Keep it cheap
    #     )
    #     result = json.loads(resp.choices[0].message.content)
    #
    #     if result.get("valid", True):
    #         return None
    #     return ValidationWarning(message=result.get("issue", "Event seems suspicious"))
    #
    # except Exception:
    #     # If sanity check fails, don't block the event
    #     return None
