"""E2E test fixtures — provides test calendar ID and cleanup utilities.

E2E tests call server tool functions directly or via MCP protocol,
both requiring a real Calendar.app test calendar.
"""

import json
import os

import pytest

from apple_calendar_mcp.calendar_connector import CalendarConnector, run_applescript

TEST_CALENDAR = os.environ.get("CALENDAR_TEST_NAME", "MCP-Test-Calendar")


@pytest.fixture
def test_calendar_id():
    """Resolve the test calendar name to its UUID."""
    if os.environ.get("CALENDAR_TEST_MODE") != "true":
        pytest.skip("E2E tests require CALENDAR_TEST_MODE=true")
    c = CalendarConnector(enable_safety_checks=True)
    calendars = c.get_calendars()
    cal = next((x for x in calendars if x["name"] == TEST_CALENDAR), None)
    if cal is None:
        pytest.skip("Test calendar not found")
    return cal["calendar_id"]


@pytest.fixture
def cleanup_uids():
    """Collect event UIDs for cleanup after test.

    Usage:
        def test_something(cleanup_uids, test_calendar_id):
            uid = create_event(...)
            cleanup_uids.append(uid)
    """
    uids = []
    yield uids
    # Cleanup via AppleScript (doesn't need calendar_id)
    for uid in uids:
        try:
            script = f'''tell application "Calendar"
    tell calendar "{TEST_CALENDAR}"
        set matchingEvents to (every event whose uid is "{uid}")
        repeat with evt in matchingEvents
            delete evt
        end repeat
    end tell
end tell'''
            run_applescript(script)
        except Exception:
            pass
