import os, requests
from dateutil import tz
import msal
from datetime import timezone

DEFAULT_SCOPES = ['Calendars.ReadWrite', 'offline_access']

def _get_app():
    client_id = os.getenv('MS_CLIENT_ID')
    tenant = os.getenv('MS_TENANT_ID', 'common')
    if not client_id:
        raise RuntimeError('Missing MS_CLIENT_ID env var.')
    authority = f'https://login.microsoftonline.com/{tenant}'
    return msal.PublicClientApplication(client_id=client_id, authority=authority)

def _acquire_token():
    app = _get_app()
    accounts = app.get_accounts()
    if accounts:
        result = app.acquire_token_silent(DEFAULT_SCOPES, account=accounts[0])
        if result and 'access_token' in result:
            return result['access_token']
    flow = app.initiate_device_flow(scopes=DEFAULT_SCOPES)
    if 'user_code' not in flow:
        raise RuntimeError('Failed to create device flow. Check app registration.')
    print(f"To sign in, visit {flow['verification_uri']} and enter code: {flow['user_code']}")
    result = app.acquire_token_by_device_flow(flow)
    if 'access_token' not in result:
        raise RuntimeError(f"Auth error: {result.get('error_description', 'Unknown')}")
    return result['access_token']

def add_event_to_ms(ev: dict) -> str:
    start = ev['start']
    end = ev['end']
    if start.tzinfo is None:
        start = start.replace(tzinfo=tz.tzlocal())
    if end.tzinfo is None:
        end = end.replace(tzinfo=tz.tzlocal())
    start_utc = start.astimezone(timezone.utc).isoformat().replace('+00:00', 'Z')
    end_utc = end.astimezone(timezone.utc).isoformat().replace('+00:00', 'Z')

    payload = {
        'subject': ev.get('summary', 'Untitled Event'),
        'body': {'contentType': 'HTML', 'content': ev.get('description', '')},
        'start': {'dateTime': start_utc, 'timeZone': 'UTC'},
        'end': {'dateTime': end_utc, 'timeZone': 'UTC'},
    }

    token = _acquire_token()
    headers = {'Authorization': f'Bearer {token}', 'Content-Type': 'application/json'}
    resp = requests.post('https://graph.microsoft.com/v1.0/me/events', headers=headers, json=payload, timeout=60)
    if resp.status_code >= 300:
        raise RuntimeError(f'Graph error [{resp.status_code}]: {resp.text}')
    return resp.json().get('id', '<no-id>')
