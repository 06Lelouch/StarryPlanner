from icalendar import Calendar, Event
from dateutil import tz

def save_event_as_ics(ev: dict, path: str):
    """Save a single event to an .ics file.
    `ev` expects keys: summary, description, start (datetime), end (datetime)
    """
    cal = Calendar()
    cal.add('prodid', '-//AI Scheduler Desktop//EN')
    cal.add('version', '2.0')

    event = Event()
    event.add('summary', ev.get('summary', 'Untitled Event'))
    if ev.get('description'):
        event.add('description', ev['description'])

    start = ev['start']
    end = ev['end']
    if start.tzinfo is None:
        start = start.replace(tzinfo=tz.tzlocal())
    if end.tzinfo is None:
        end = end.replace(tzinfo=tz.tzlocal())

    event.add('dtstart', start)
    event.add('dtend', end)

    cal.add_component(event)
    with open(path, 'wb') as f:
        f.write(cal.to_ical())
