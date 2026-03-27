"""Integration test fixtures — manages test calendar lifecycle.

Creates an MCP-Test-Calendar in Calendar.app before the test session
and removes it (with all events) after the session completes.
"""

import os

import pytest

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

    Used by recurring event tests where events can't be fully deleted
    via the API — the calendar must be recreated to ensure clean state.

    WARNING: Not compatible with parallel test execution (pytest-xdist).
    """
    delete_all_test_calendars(TEST_CALENDAR)
    create_test_calendar(TEST_CALENDAR)
    yield
    try:
        delete_all_test_calendars(TEST_CALENDAR)
    finally:
        # Always recreate, even if delete failed or was partial
        if not calendar_exists(TEST_CALENDAR):
            create_test_calendar(TEST_CALENDAR)
