import argparse
import calendar
import datetime
import os
import sys
from typing import Any

from google_service import Create_Service
from schedule_parser import Shift, get_shifts_from_text

sys.dont_write_bytecode = True

CLIENT_SECRET_FILE = os.environ.get('GOOGLE_CLIENT_SECRET_FILE', 'credentials.json')
API_NAME = 'calendar'
API_VERSION = 'v3'
SCOPES = ['https://www.googleapis.com/auth/calendar']
LOCATION = os.environ.get('CALENDAR_LOCATION', '517 Richmond Street East, Toronto, ON M5A 1R4')
WORK_CALENDAR_ID = os.environ.get('GOOGLE_CALENDAR_ID', 'iqum5089gg20ev7s3vdo05pqfg@group.calendar.google.com')
work_calendar_id = WORK_CALENDAR_ID  # Maintained for backwards compatibility
TIMEZONE_OFFSET = os.environ.get('CALENDAR_TIMEZONE_OFFSET', '-04:00')
service = None


def build_event_body(
    shift: Shift,
    location: str = LOCATION,
    timezone_offset: str = TIMEZONE_OFFSET,
    color_id: Any = 11,
) -> dict[str, Any]:
    """Constructs the Google Calendar event payload from a Shift object."""
    try:
        start_date = datetime.date(shift.get_year(), shift.get_month(), shift.get_date())
    except ValueError:
        # Clamp invalid day of month e.g. day 31 in a 30-day month
        max_days = calendar.monthrange(shift.get_year(), shift.get_month())[1]
        clamped_day = min(shift.get_date(), max_days)
        start_date = datetime.date(shift.get_year(), shift.get_month(), clamped_day)

    # If the end time is less than or equal to start time, the shift crosses midnight
    if (shift.get_end_hour(), shift.get_end_minute()) <= (shift.get_start_hour(), shift.get_start_minute()):
        end_date = start_date + datetime.timedelta(days=1)
    else:
        end_date = start_date

    start_dt = (
        f"{start_date.year:04d}-{start_date.month:02d}-{start_date.day:02d}T"
        f"{shift.get_start_hour():02d}:{shift.get_start_minute():02d}:00{timezone_offset}"
    )
    end_dt = (
        f"{end_date.year:04d}-{end_date.month:02d}-{end_date.day:02d}T"
        f"{shift.get_end_hour():02d}:{shift.get_end_minute():02d}:00{timezone_offset}"
    )

    return {
        'start': {'dateTime': start_dt},
        'end': {'dateTime': end_dt},
        'summary': 'Work',
        'description': shift.get_role(),
        'colorId': color_id,
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
    calendar_service: Any | None = None,
    calendar_id: str = WORK_CALENDAR_ID,
    shifts: list[Shift] | None = None,
    location: str = LOCATION,
    timezone_offset: str = TIMEZONE_OFFSET,
    dry_run: bool = False,
    month: int | None = None,
    year: int | None = None,
) -> list[dict[str, Any]]:
    """Fetches shifts from text/OCR and inserts them into the target Google Calendar."""
    global service

    if not dry_run and calendar_service is None:
        calendar_service = Create_Service(CLIENT_SECRET_FILE, API_NAME, API_VERSION, SCOPES)
        service = calendar_service

    if not dry_run and not calendar_service:
        print("Failed to initialize Google Calendar service.")
        return []

    created_events = []
    if shifts is None:
        shifts = get_shifts_from_text(month=month, year=year)

    for shift in shifts:
        event_request_body = build_event_body(
            shift,
            location=location,
            timezone_offset=timezone_offset,
        )

        if dry_run:
            print(
                f"[DRY RUN] Would create event: {shift.get_role()} on "
                f"{shift.get_year()}-{shift.get_month():02d}-{shift.get_date():02d} "
                f"({event_request_body['start']['dateTime']} to {event_request_body['end']['dateTime']})"
            )
            created_events.append({'id': 'dry_run_id', 'status': 'confirmed', 'body': event_request_body})
            continue

        try:
            event = calendar_service.events().insert(
                calendarId=calendar_id,
                sendUpdates='none',
                sendNotifications=True,
                body=event_request_body,
            ).execute()
            created_events.append(event)
            print(f"Created event: {shift.get_role()} on {shift.get_year()}-{shift.get_month():02d}-{shift.get_date():02d}")
        except Exception as e:
            print(f"Error creating event for shift ({shift.get_role()} on {shift.get_year()}-{shift.get_month():02d}-{shift.get_date():02d}): {e}")

    return created_events


def main() -> None:
    parser = argparse.ArgumentParser(description="Sync work shifts to Google Calendar")
    parser.add_argument('--calendar-id', default=WORK_CALENDAR_ID, help="Google Calendar ID")
    parser.add_argument('--location', default=LOCATION, help="Location of work shifts")
    parser.add_argument('--timezone-offset', default=TIMEZONE_OFFSET, help="Timezone offset e.g. -04:00")
    parser.add_argument('--month', type=int, default=None, help="Schedule month number (1-12)")
    parser.add_argument('--year', type=int, default=None, help="Schedule year")
    parser.add_argument('--dry-run', action='store_true', help="Preview events without modifying calendar")
    args = parser.parse_args()

    sync_shifts_to_calendar(
        calendar_id=args.calendar_id,
        location=args.location,
        timezone_offset=args.timezone_offset,
        dry_run=args.dry_run,
        month=args.month,
        year=args.year,
    )


if __name__ == '__main__':
    main()
