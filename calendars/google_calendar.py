from __future__ import annotations
from dateutil import tz
from google.oauth2.credentials import Credentials
from google_auth_oauthlib.flow import InstalledAppFlow
from googleapiclient.discovery import build
from google.auth.transport.requests import Request

SCOPES = ['https://www.googleapis.com/auth/calendar.events']

def is_authenticated() -> bool:
    """Check if valid Google credentials exist without triggering OAuth."""
    try:
        creds = Credentials.from_authorized_user_file('token.json', SCOPES)
        if creds and creds.valid:
            return True
        if creds and creds.expired and creds.refresh_token:
            creds.refresh(Request())
            with open('token.json', 'w') as token:
                token.write(creds.to_json())
            return True
        return False
    except Exception:
        return False

def _ensure_creds():
    creds = None
    try:
        creds = Credentials.from_authorized_user_file('token.json', SCOPES)
    except Exception:
        creds = None
    if not creds or not creds.valid:
        if creds and creds.expired and creds.refresh_token:
            creds.refresh(Request())
        else:
            flow = InstalledAppFlow.from_client_secrets_file(
                'google_client_secret.json', SCOPES
            )
            creds = flow.run_local_server(port=0)
        with open('token.json', 'w') as token:
            token.write(creds.to_json())
    return creds

def add_event_to_google(ev: dict) -> str:
    start = ev['start']
    end = ev['end']
    if start.tzinfo is None:
        start = start.replace(tzinfo=tz.tzlocal())
    if end.tzinfo is None:
        end = end.replace(tzinfo=tz.tzlocal())

    body = {
        'summary': ev.get('summary', 'Untitled Event'),
        'description': ev.get('description', ''),
        'start': {'dateTime': start.isoformat()},
        'end': {'dateTime': end.isoformat()},
    }

    # Add recurrence if specified (list of RRULE strings)
    if ev.get('recurrence'):
        body['recurrence'] = ev['recurrence']

    creds = _ensure_creds()
    service = build('calendar', 'v3', credentials=creds)
    created = service.events().insert(calendarId='primary', body=body).execute()
    return {
        "id": created.get("id"),
        "htmlLink": created.get("htmlLink"),
        "summary": created.get("summary"),
        "start": (created.get("start") or {}).get("dateTime"),
        "end":   (created.get("end")   or {}).get("dateTime"),
        "recurrence": created.get("recurrence"),  # List of RRULE strings or None
    }
