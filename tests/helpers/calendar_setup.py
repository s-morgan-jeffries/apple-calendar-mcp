"""Test calendar setup and teardown utilities.

Reusable from pytest fixtures, standalone scripts, or CI.
"""

from apple_calendar_mcp.calendar_connector import run_applescript

DEFAULT_CALENDAR_NAME = "MCP-Test-Calendar"


def calendar_exists(name: str = DEFAULT_CALENDAR_NAME) -> bool:
    """Check if a calendar with the given name exists in Calendar.app."""
    names = run_applescript('tell application "Calendar" to name of every calendar')
    return name in [n.strip() for n in names.split(",")]


def create_test_calendar(name: str = DEFAULT_CALENDAR_NAME) -> bool:
    """Create the test calendar if it doesn't already exist.

    Returns True if the calendar was created, False if it already existed.
    """
    if calendar_exists(name):
        return False
    run_applescript(
        f'tell application "Calendar" to make new calendar with properties {{name:"{name}"}}'
    )
    return True


def delete_test_calendar(name: str = DEFAULT_CALENDAR_NAME) -> bool:
    """Delete the test calendar if it exists.

    Returns True if the calendar was deleted, False if it didn't exist.
    """
    if not calendar_exists(name):
        return False
    run_applescript(f'tell application "Calendar" to delete calendar "{name}"')
    return True


def cleanup_test_events(name: str = DEFAULT_CALENDAR_NAME) -> None:
    """Delete all events from the test calendar without removing the calendar itself."""
    script = f'''tell application "Calendar"
    tell calendar "{name}"
        delete every event
    end tell
end tell'''
    run_applescript(script)
