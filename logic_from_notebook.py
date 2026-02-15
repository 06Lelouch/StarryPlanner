# ---- 1. Imports ----
import sys, os, json, pytz
from datetime import datetime
from typing import Tuple, List
from openai import OpenAI
from dotenv import load_dotenv

from validation import (
    get_input_validator,
    get_event_validator,
    sanity_check_event,
    ValidationWarning,
)

# ---- 1b. Path helper for PyInstaller bundled .exe ----
def _base_path():
    """Return the directory where the app lives (works for dev and .exe)."""
    if getattr(sys, 'frozen', False):
        return os.path.dirname(sys.executable)
    return os.path.dirname(os.path.abspath(__file__))

# ---- 2. Load environment and initialize client ----
load_dotenv(os.path.join(_base_path(), '.env'))
client = OpenAI(api_key=os.getenv("OPENAI_API_KEY"))
assert client.api_key, "OPENAI_API_KEY not found in environment"
print("Loaded OpenAI key, length:", len(client.api_key))

# ---- 3. Define event schema for structured extraction ----
extract_event_schema = [
    {
        "name": "extract_event",
        "description": "Parse a scheduling request into structured event fields",
        "parameters": {
            "type": "object",
            "properties": {
                "title":     {"type": "string", "description": "A short event title"},
                "date":      {"type": "string", "description": "YYYY-MM-DD (first occurrence for recurring events)"},
                "start":     {"type": "string", "description": "HH:MM, 24-hour"},
                "end":       {"type": "string", "description": "HH:MM, 24-hour"},
                "tz":        {"type": "string", "description": "IANA timezone, e.g. America/Toronto"},
                "location":  {"type": "string", "description": "Optional location or URL"},
                "notes":     {"type": "string", "description": "Optional notes or description"},
                "recurrence": {
                    "type": "string",
                    "description": "Optional RRULE for recurring events (without 'RRULE:' prefix). "
                                   "Examples: 'FREQ=DAILY', 'FREQ=WEEKLY;BYDAY=MO,WE,FR', "
                                   "'FREQ=WEEKLY;COUNT=10', 'FREQ=MONTHLY;BYMONTHDAY=15', "
                                   "'FREQ=YEARLY'. Leave empty/null for one-time events."
                },
            },
            "required": ["title", "date", "start", "end", "tz"],
        },
    }
]

# ---- 4. Helper: get current timezone info ----
def _get_local_context():
    """Return ISO time string and timezone name for now."""
    local_now = datetime.now().astimezone()
    local_tzinfo = local_now.tzinfo
    tzname = getattr(local_tzinfo, "key", local_tzinfo.tzname(None))
    now_iso = local_now.strftime("%Y-%m-%dT%H:%M:%S%z")
    return now_iso, tzname


# ---- 5. Core: extract event details via LLM ----
def extract_slots(nl: str, now_iso: str, tzname: str) -> dict:
    """
    Send the user's natural-language scheduling request to OpenAI,
    return structured event fields.
    """
    system_prompt = (
        f"You are a helpful scheduling assistant. The current date/time is {now_iso} "
        f"in timezone {tzname}. Interpret relative terms like 'tomorrow' or 'next Friday' "
        "based on this context. Return JSON ONLY by calling the extract_event function."
    )

    resp = client.chat.completions.create(
        model="gpt-5-nano",
        messages=[
            {"role": "system", "content": system_prompt},
            {"role": "user", "content": nl},
        ],
        functions=extract_event_schema,
        function_call={"name": "extract_event"},
    )

    fn = resp.choices[0].message.function_call
    return json.loads(fn.arguments)


# ---- 6. Main: build event dict for Google Calendar ----
def build_event_dict_from_prompt(prompt: str) -> Tuple[dict, List[ValidationWarning]]:
    """
    Takes a natural-language scheduling request and returns
    a dictionary ready to send to Google Calendar, plus any warnings.

    Returns:
        Tuple of (event_dict, list_of_warnings)
        - event_dict: Ready for Google Calendar API
        - warnings: Soft issues user should confirm (may be empty)

    Raises:
        ValidationError subclasses for hard errors (must fix)
    """
    # 1. PRE-GPT: Validate and sanitize input
    input_validator = get_input_validator()
    sanitized_prompt = input_validator.validate_and_sanitize(prompt)

    # 2. Get context (current time & timezone)
    now_iso, tzname = _get_local_context()

    # 3. Parse the user's natural-language request via GPT
    ev = extract_slots(sanitized_prompt, now_iso, tzname)

    # 4. POST-GPT: Validate event data (hard checks + soft warnings)
    event_validator = get_event_validator()
    ev, warnings = event_validator.validate_event(ev)

    # 5. Convert strings → timezone-aware datetimes
    tz = pytz.timezone(ev["tz"])
    start_dt = tz.localize(datetime.fromisoformat(f"{ev['date']}T{ev['start']}"))
    end_dt   = tz.localize(datetime.fromisoformat(f"{ev['date']}T{ev['end']}"))

    # 6. AUTO-FIX: Swap if end < start
    if end_dt < start_dt:
        start_dt, end_dt = end_dt, start_dt

    # 7. Check time constraints (adds warnings, doesn't raise)
    warnings.extend(event_validator.check_time_constraints(start_dt, end_dt))

    # 8. Build event dict
    event = {
        "summary": ev["title"],
        "description": ev.get("notes", "Added via AI Scheduler"),
        "start": start_dt,
        "end": end_dt,
    }

    if ev.get("location"):
        event["description"] += f"\nLocation: {ev['location']}"

    # 9. Add recurrence if specified
    if ev.get("recurrence"):
        rrule = ev["recurrence"]
        # Ensure RRULE prefix
        if not rrule.upper().startswith("RRULE:"):
            rrule = f"RRULE:{rrule}"
        event["recurrence"] = [rrule]

    # 10. GPT sanity check (DISABLED - always returns None for now)
    sanity_warning = sanity_check_event(ev)
    if sanity_warning:
        warnings.append(sanity_warning)

    return event, warnings


# ---- 7. Optional standalone test ----
if __name__ == "__main__":
    from validation import ValidationError

    print("AI Scheduler logic test mode.")
    user_prompt = input("Describe your event (e.g. 'meeting with Bob tomorrow 3–4pm'): ").strip()
    if user_prompt:
        try:
            ev, warnings = build_event_dict_from_prompt(user_prompt)

            print("\n--- Event ---")
            print(json.dumps({
                "summary": ev["summary"],
                "start": ev["start"].isoformat(),
                "end": ev["end"].isoformat(),
                "description": ev["description"],
            }, indent=2))

            if warnings:
                print("\n--- Warnings ---")
                for w in warnings:
                    print(f"  - {w.message}")
            else:
                print("\n(No warnings)")

        except ValidationError as e:
            print(f"\nValidation Error: {e.user_message}")