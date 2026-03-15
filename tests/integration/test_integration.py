"""Integration tests for Apple Calendar MCP — runs against real Calendar.app.

Requires:
    - CALENDAR_TEST_MODE=true environment variable
    - A calendar named "MCP-Test-Calendar" in Calendar.app

Run with: make test-integration
"""
import os
import re
import pytest

from apple_calendar_mcp.calendar_connector import CalendarConnector, run_applescript


# Skip entire module if not in test mode
pytestmark = pytest.mark.skipif(
    os.environ.get("CALENDAR_TEST_MODE") != "true",
    reason="Integration tests require CALENDAR_TEST_MODE=true",
)


@pytest.fixture
def connector():
    """Create a CalendarConnector with safety checks enabled."""
    return CalendarConnector(enable_safety_checks=True)


class TestGetCalendarsIntegration:
    """Integration tests for get_calendars against real Calendar.app."""

    def test_returns_non_empty_list(self, connector):
        """Real Calendar.app should have at least one calendar."""
        calendars = connector.get_calendars()
        assert isinstance(calendars, list)
        assert len(calendars) > 0

    def test_test_calendar_exists(self, connector):
        """MCP-Test-Calendar should be present."""
        calendars = connector.get_calendars()
        names = [c["name"] for c in calendars]
        assert "MCP-Test-Calendar" in names

    def test_calendar_has_required_keys(self, connector):
        """Each calendar should have name, writable, description, color."""
        calendars = connector.get_calendars()
        for cal in calendars:
            assert "name" in cal, f"Missing 'name' in calendar: {cal}"
            assert "writable" in cal, f"Missing 'writable' in calendar: {cal}"
            assert "description" in cal, f"Missing 'description' in calendar: {cal}"
            assert "color" in cal, f"Missing 'color' in calendar: {cal}"

    def test_writable_is_boolean(self, connector):
        """Writable should be a proper boolean."""
        calendars = connector.get_calendars()
        for cal in calendars:
            assert isinstance(cal["writable"], bool), (
                f"writable should be bool, got {type(cal['writable'])} for {cal['name']}"
            )

    def test_test_calendar_is_writable(self, connector):
        """MCP-Test-Calendar should be writable."""
        calendars = connector.get_calendars()
        test_cal = next(c for c in calendars if c["name"] == "MCP-Test-Calendar")
        assert test_cal["writable"] is True

    def test_color_is_hex_string(self, connector):
        """Color should be a hex color string like #RRGGBB."""
        calendars = connector.get_calendars()
        for cal in calendars:
            color = cal["color"]
            assert isinstance(color, str), f"color should be str for {cal['name']}"
            assert color.startswith("#"), f"color should start with # for {cal['name']}"
            assert len(color) == 7, f"color should be #RRGGBB format for {cal['name']}"


class TestCreateEventIntegration:
    """Integration tests for create_event against real Calendar.app."""

    TEST_CALENDAR = "MCP-Test-Calendar"

    def _delete_event_by_uid(self, uid: str):
        """Clean up a created event by UID."""
        script = f'''tell application "Calendar"
    tell calendar "{self.TEST_CALENDAR}"
        set matchingEvents to (every event whose uid is "{uid}")
        repeat with evt in matchingEvents
            delete evt
        end repeat
    end tell
end tell'''
        try:
            run_applescript(script)
        except Exception:
            pass  # Best-effort cleanup

    def test_creates_event_and_returns_uid(self, connector):
        """Creating an event should return a valid UID string."""
        uid = connector.create_event(
            calendar_name=self.TEST_CALENDAR,
            summary="Integration Test Event",
            start_date="2026-06-15T10:00:00",
            end_date="2026-06-15T11:00:00",
        )
        try:
            assert isinstance(uid, str)
            assert len(uid) > 0
            # UIDs are typically UUID format
            assert re.match(r"^[A-F0-9-]+$", uid, re.IGNORECASE), f"UID doesn't look like UUID: {uid}"
        finally:
            self._delete_event_by_uid(uid)

    def test_created_event_has_correct_summary(self, connector):
        """Verify the created event has the right summary via AppleScript query."""
        uid = connector.create_event(
            calendar_name=self.TEST_CALENDAR,
            summary="Verify Summary Test",
            start_date="2026-06-15T14:00:00",
            end_date="2026-06-15T15:00:00",
        )
        try:
            script = f'''tell application "Calendar"
    tell calendar "{self.TEST_CALENDAR}"
        set evt to first event whose uid is "{uid}"
        return summary of evt
    end tell
end tell'''
            result = run_applescript(script)
            assert result == "Verify Summary Test"
        finally:
            self._delete_event_by_uid(uid)

    def test_creates_event_with_optional_fields(self, connector):
        """Creating an event with location, description, and URL should succeed."""
        uid = connector.create_event(
            calendar_name=self.TEST_CALENDAR,
            summary="Full Event Test",
            start_date="2026-06-15T09:00:00",
            end_date="2026-06-15T10:00:00",
            location="Conference Room B",
            description="Test description with details",
            url="https://example.com/test",
        )
        try:
            assert isinstance(uid, str)
            assert len(uid) > 0
            # Verify location was set
            script = f'''tell application "Calendar"
    tell calendar "{self.TEST_CALENDAR}"
        set evt to first event whose uid is "{uid}"
        return location of evt
    end tell
end tell'''
            result = run_applescript(script)
            assert result == "Conference Room B"
        finally:
            self._delete_event_by_uid(uid)

    def test_creates_allday_event(self, connector):
        """Creating an all-day event should set the allday flag."""
        uid = connector.create_event(
            calendar_name=self.TEST_CALENDAR,
            summary="All Day Test",
            start_date="2026-06-15",
            end_date="2026-06-16",
            allday_event=True,
        )
        try:
            assert isinstance(uid, str)
            script = f'''tell application "Calendar"
    tell calendar "{self.TEST_CALENDAR}"
        set evt to first event whose uid is "{uid}"
        return allday event of evt
    end tell
end tell'''
            result = run_applescript(script)
            assert result == "true"
        finally:
            self._delete_event_by_uid(uid)
