import sys

sys.dont_write_bytecode = True

from typing import Any, Optional

from google_service import Create_Service, convert_to_RFC_datetime
from schedule_parser import Shift, get_shifts_from_text

CLIENT_SECRET_FILE = 'credentials.json'
API_NAME = 'calendar'
API_VERSION = 'v3'
SCOPES = ['https://www.googleapis.com/auth/calendar']
LOCATION = '517 Richmond Street East, Toronto, ON M5A 1R4'
WORK_CALENDAR_ID = 'iqum5089gg20ev7s3vdo05pqfg@group.calendar.google.com'
work_calendar_id = WORK_CALENDAR_ID  # Maintained for backwards compatibility
TIMEZONE_OFFSET = '-04:00'
service = None


def build_event_body(shift: Shift, location: str = LOCATION, timezone_offset: str = TIMEZONE_OFFSET) -> dict[str, Any]:
    """Constructs the Google Calendar event payload from a Shift object."""
    start_dt = (
        convert_to_RFC_datetime(
            shift.get_year(),
            shift.get_month(),
            shift.get_date(),
            shift.get_start_hour(),
            shift.get_start_minute(),
        )[:19]
        + timezone_offset
    )
    end_dt = (
        convert_to_RFC_datetime(
            shift.get_year(),
            shift.get_month(),
            shift.get_date(),
            shift.get_end_hour(),
            shift.get_end_minute(),
        )[:19]
        + timezone_offset
    )

    return {
        'start': {'dateTime': start_dt},
        'end': {'dateTime': end_dt},
        'summary': 'Work',
        'description': shift.get_role(),
        'colorId': 11,
        'status': 'confirmed',
        'location': location,
        'reminders': {
            'useDefault': False,
            'overrides': [
                {'method': 'popup', 'minutes': 60 * 14}
            ],
        },
    }


def sync_shifts_to_calendar(
    calendar_service: Optional[Any] = None,
    calendar_id: str = WORK_CALENDAR_ID,
) -> list[dict[str, Any]]:
    """Fetches shifts from text/OCR and inserts them into the target Google Calendar."""
    global service
    if calendar_service is None:
        calendar_service = Create_Service(CLIENT_SECRET_FILE, API_NAME, API_VERSION, SCOPES)
        service = calendar_service

    if not calendar_service:
        print("Failed to initialize Google Calendar service.")
        return []

    created_events = []
    shifts = get_shifts_from_text()

    for shift in shifts:
        event_request_body = build_event_body(shift)
        event = calendar_service.events().insert(
            calendarId=calendar_id,
            sendUpdates='none',
            sendNotifications=True,
            body=event_request_body,
        ).execute()
        created_events.append(event)
        print(f"Created event: {shift.get_role()} on {shift.get_year()}-{shift.get_month():02d}-{shift.get_date():02d}")

    return created_events


if __name__ == '__main__':
    sync_shifts_to_calendar()
