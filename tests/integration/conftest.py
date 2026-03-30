"""Integration test fixtures — manages test calendar lifecycle.

Creates an MCP-Test-Calendar in Calendar.app before the test session
and removes it (with all events) after the session completes.
"""

import os

import pytest

from apple_calendar_mcp.calendar_connector import CalendarConnector
from tests.helpers.calendar_setup import (
    calendar_exists,
    create_test_calendar,
    delete_all_test_calendars,
    delete_test_calendar,
)

TEST_CALENDAR = os.environ.get("CALENDAR_TEST_NAME", "MCP-Test-Calendar")


@pytest.fixture(scope="session", autouse=True)
def ensure_test_calendar():
    """Create the test calendar before tests, delete it after."""
    if os.environ.get("CALENDAR_TEST_MODE") != "true":
        yield
        return

    created = create_test_calendar(TEST_CALENDAR)

    yield

    if created and calendar_exists(TEST_CALENDAR):
        delete_all_test_calendars(TEST_CALENDAR)


@pytest.fixture
def fresh_calendar():
    """Provide a clean test calendar for tests that need full calendar reset.

    Yields the fresh calendar_id since recreation changes the UUID.

    WARNING: Not compatible with parallel test execution (pytest-xdist).
    """
    delete_all_test_calendars(TEST_CALENDAR)
    create_test_calendar(TEST_CALENDAR)
    # Resolve the fresh calendar ID
    c = CalendarConnector(enable_safety_checks=True)
    calendars = c.get_calendars()
    cal = next((x for x in calendars if x["name"] == TEST_CALENDAR), None)
    yield cal["calendar_id"] if cal else None
    try:
        delete_all_test_calendars(TEST_CALENDAR)
    finally:
        if not calendar_exists(TEST_CALENDAR):
            create_test_calendar(TEST_CALENDAR)


@pytest.fixture
def test_calendar_id():
    """Resolve the test calendar name to its UUID (fresh each test)."""
    if os.environ.get("CALENDAR_TEST_MODE") != "true":
        return None
    c = CalendarConnector(enable_safety_checks=True)
    calendars = c.get_calendars()
    cal = next((x for x in calendars if x["name"] == TEST_CALENDAR), None)
    if cal is None:
        return None
    return cal["calendar_id"]
