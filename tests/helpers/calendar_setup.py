"""Test calendar setup and teardown utilities.

Reusable from pytest fixtures, standalone scripts, or CI.
"""

import json
import os

from apple_calendar_mcp.calendar_connector import run_applescript, run_swift_helper

DEFAULT_CALENDAR_NAME = "MCP-Test-Calendar"
DEFAULT_CALENDAR_SOURCE = os.environ.get("CALENDAR_TEST_SOURCE", "iCloud")


def calendar_exists(name: str = DEFAULT_CALENDAR_NAME) -> bool:
    """Check if a calendar with the given name exists in Calendar.app."""
    result = run_swift_helper("get_calendars", [])
    calendars = json.loads(result)
    return any(c["name"] == name for c in calendars)


def create_test_calendar(name: str = DEFAULT_CALENDAR_NAME) -> bool:
    """Create the test calendar if it doesn't already exist.

    Uses CALENDAR_TEST_SOURCE env var for the source (default: iCloud).
    Returns True if the calendar was created, False if it already existed.
    """
    if calendar_exists(name):
        return False
    args = ["--name", name]
    if DEFAULT_CALENDAR_SOURCE:
        args += ["--source", DEFAULT_CALENDAR_SOURCE]
    run_swift_helper("create_calendar", args)
    return True


def delete_test_calendar(name: str = DEFAULT_CALENDAR_NAME) -> bool:
    """Delete the test calendar if it exists.

    Returns True if the calendar was deleted, False if it didn't exist.
    """
    if not calendar_exists(name):
        return False
    run_swift_helper("delete_calendar", ["--name", name])
    return True


def cleanup_test_events(name: str = DEFAULT_CALENDAR_NAME) -> None:
    """Delete all events from the test calendar without removing the calendar itself."""
    script = f'''tell application "Calendar"
    tell calendar "{name}"
        delete every event
    end tell
end tell'''
    run_applescript(script)
