"""Manual developer smoke script for Google Calendar read-only integration.

Usage:
    python scripts/google_calendar_smoke.py

Requires GOOGLE_CALENDAR_CREDENTIALS_FILE or GOOGLE_CALENDAR_TOKEN_FILE to be configured.
This script is for interactive local testing and is NOT run by automated test suites.
"""

import sys
from datetime import datetime, timedelta
from zoneinfo import ZoneInfo

from googleapiclient.discovery import build

from medsemiotics.integrations.google_calendar.auth import get_calendar_credentials
from medsemiotics.integrations.google_calendar.client import GoogleCalendarReader
from medsemiotics.integrations.google_calendar.exceptions import (
    GoogleCalendarAuthError,
    GoogleCalendarError,
)


def main() -> None:
    """Run interactive smoke test of Google Calendar reader."""
    print("=== MedSemiotics Google Calendar Read Smoke Test ===")
    try:
        creds = get_calendar_credentials(interactive=True)
        print("✓ Authentication successful.")
    except GoogleCalendarAuthError as err:
        print(f"✗ Authentication failed: {err}", file=sys.stderr)
        sys.exit(1)

    try:
        service = build("calendar", "v3", credentials=creds)
        reader = GoogleCalendarReader(service, default_timezone=ZoneInfo("UTC"))
        calendars = reader.list_calendars()
        print(f"✓ Found {len(calendars)} accessible calendars:")
        for cal in calendars:
            primary_tag = " (Primary)" if cal.primary else ""
            print(f"  - [{cal.calendar_id}] {cal.name}{primary_tag}")

        if calendars:
            primary_cal = next((c for c in calendars if c.primary), calendars[0])
            now = datetime.now(ZoneInfo("UTC"))
            week_later = now + timedelta(days=7)
            print(
                f"\nListing events for next 7 days in '{primary_cal.name}' "
                f"({primary_cal.calendar_id})..."
            )
            events = reader.list_events(
                calendar_id=primary_cal.calendar_id,
                time_min=now,
                time_max=week_later,
            )
            print(f"✓ Retrieved {len(events)} events:")
            for ev in events:
                print(
                    f"  - [{ev.start.isoformat()} .. {ev.end.isoformat()}] "
                    f"{ev.title} (ID: {ev.event_id})"
                )

    except GoogleCalendarError as err:
        print(f"✗ Google Calendar API read failed: {err}", file=sys.stderr)
        sys.exit(1)


if __name__ == "__main__":
    main()
