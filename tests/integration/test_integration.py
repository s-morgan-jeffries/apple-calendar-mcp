"""Integration tests for Apple Calendar MCP — runs against real Calendar.app.

Requires:
    - CALENDAR_TEST_MODE=true environment variable
    - The test calendar is created/deleted automatically by conftest.py

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

TEST_CALENDAR = os.environ.get("CALENDAR_TEST_NAME", "MCP-Test-Calendar")


@pytest.fixture
def connector():
    """Create a CalendarConnector with safety checks enabled."""
    return CalendarConnector(enable_safety_checks=True)


def _delete_event_by_uid(uid: str):
    """Clean up a created event by UID."""
    script = f'''tell application "Calendar"
    tell calendar "{TEST_CALENDAR}"
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

    def test_creates_event_and_returns_uid(self, connector):
        """Creating an event should return a valid UID string."""
        uid = connector.create_event(
            calendar_name=TEST_CALENDAR,
            summary="Integration Test Event",
            start_date="2026-06-15T10:00:00",
            end_date="2026-06-15T11:00:00",
        )
        try:
            assert isinstance(uid, str)
            assert len(uid) > 0
            assert re.match(r"^[A-F0-9-]+$", uid, re.IGNORECASE), f"UID doesn't look like UUID: {uid}"
        finally:
            _delete_event_by_uid(uid)

    def test_created_event_has_correct_summary(self, connector):
        """Verify the created event has the right summary via AppleScript query."""
        uid = connector.create_event(
            calendar_name=TEST_CALENDAR,
            summary="Verify Summary Test",
            start_date="2026-06-15T14:00:00",
            end_date="2026-06-15T15:00:00",
        )
        try:
            script = f'''tell application "Calendar"
    tell calendar "{TEST_CALENDAR}"
        set evt to first event whose uid is "{uid}"
        return summary of evt
    end tell
end tell'''
            result = run_applescript(script)
            assert result == "Verify Summary Test"
        finally:
            _delete_event_by_uid(uid)

    def test_creates_event_with_optional_fields(self, connector):
        """Creating an event with location, description, and URL should succeed."""
        uid = connector.create_event(
            calendar_name=TEST_CALENDAR,
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
            script = f'''tell application "Calendar"
    tell calendar "{TEST_CALENDAR}"
        set evt to first event whose uid is "{uid}"
        return location of evt
    end tell
end tell'''
            result = run_applescript(script)
            assert result == "Conference Room B"
        finally:
            _delete_event_by_uid(uid)

    def test_creates_allday_event(self, connector):
        """Creating an all-day event should set the allday flag."""
        uid = connector.create_event(
            calendar_name=TEST_CALENDAR,
            summary="All Day Test",
            start_date="2026-06-15",
            end_date="2026-06-16",
            allday_event=True,
        )
        try:
            assert isinstance(uid, str)
            script = f'''tell application "Calendar"
    tell calendar "{TEST_CALENDAR}"
        set evt to first event whose uid is "{uid}"
        return allday event of evt
    end tell
end tell'''
            result = run_applescript(script)
            assert result == "true"
        finally:
            _delete_event_by_uid(uid)


class TestGetEventsIntegration:
    """Integration tests for get_events against real Calendar.app via EventKit."""

    def test_get_events_returns_created_event(self, connector):
        """Create an event, then verify get_events returns it."""
        uid = connector.create_event(
            calendar_name=TEST_CALENDAR,
            summary="GetEvents Test",
            start_date="2026-07-01T10:00:00",
            end_date="2026-07-01T11:00:00",
        )
        try:
            events = connector.get_events(
                calendar_name=TEST_CALENDAR,
                start_date="2026-07-01T00:00:00",
                end_date="2026-07-02T00:00:00",
            )
            summaries = [e["summary"] for e in events]
            assert "GetEvents Test" in summaries
        finally:
            _delete_event_by_uid(uid)

    def test_date_range_filtering(self, connector):
        """Event outside date range should not be returned."""
        uid = connector.create_event(
            calendar_name=TEST_CALENDAR,
            summary="Outside Range Test",
            start_date="2026-08-01T10:00:00",
            end_date="2026-08-01T11:00:00",
        )
        try:
            events = connector.get_events(
                calendar_name=TEST_CALENDAR,
                start_date="2026-07-01T00:00:00",
                end_date="2026-07-02T00:00:00",
            )
            summaries = [e["summary"] for e in events]
            assert "Outside Range Test" not in summaries
        finally:
            _delete_event_by_uid(uid)

    def test_event_has_expected_keys(self, connector):
        """Returned event dicts should have all expected keys."""
        uid = connector.create_event(
            calendar_name=TEST_CALENDAR,
            summary="Keys Test Event",
            start_date="2026-07-02T10:00:00",
            end_date="2026-07-02T11:00:00",
            location="Test Location",
        )
        try:
            events = connector.get_events(
                calendar_name=TEST_CALENDAR,
                start_date="2026-07-02T00:00:00",
                end_date="2026-07-03T00:00:00",
            )
            test_events = [e for e in events if e["summary"] == "Keys Test Event"]
            assert len(test_events) == 1
            event = test_events[0]
            for key in ["uid", "summary", "start_date", "end_date", "allday_event",
                         "location", "description", "url", "status", "calendar_name"]:
                assert key in event, f"Missing key '{key}' in event"
            assert event["location"] == "Test Location"
            assert event["calendar_name"] == TEST_CALENDAR
        finally:
            _delete_event_by_uid(uid)

    def test_empty_date_range_returns_empty_list(self, connector):
        """Date range with no events should return empty list."""
        events = connector.get_events(
            calendar_name=TEST_CALENDAR,
            start_date="2099-01-01T00:00:00",
            end_date="2099-01-02T00:00:00",
        )
        assert events == []


class TestUpdateEventIntegration:
    """Integration tests for update_event against real Calendar.app."""

    def test_update_summary(self, connector):
        """Update summary and verify via get_events."""
        uid = connector.create_event(
            calendar_name=TEST_CALENDAR,
            summary="Original Summary",
            start_date="2026-09-01T10:00:00",
            end_date="2026-09-01T11:00:00",
        )
        try:
            connector.update_event(TEST_CALENDAR, uid, summary="Updated Summary")
            events = connector.get_events(TEST_CALENDAR, "2026-09-01T00:00:00", "2026-09-02T00:00:00")
            test_events = [e for e in events if e["uid"] == uid]
            assert len(test_events) == 1
            assert test_events[0]["summary"] == "Updated Summary"
        finally:
            _delete_event_by_uid(uid)

    def test_update_location(self, connector):
        """Update location from A to B and verify."""
        uid = connector.create_event(
            calendar_name=TEST_CALENDAR,
            summary="Location Update Test",
            start_date="2026-09-02T10:00:00",
            end_date="2026-09-02T11:00:00",
            location="Room A",
        )
        try:
            connector.update_event(TEST_CALENDAR, uid, location="Room B")
            events = connector.get_events(TEST_CALENDAR, "2026-09-02T00:00:00", "2026-09-03T00:00:00")
            test_events = [e for e in events if e["uid"] == uid]
            assert len(test_events) == 1
            assert test_events[0]["location"] == "Room B"
        finally:
            _delete_event_by_uid(uid)

    def test_update_dates(self, connector):
        """Update start/end dates and verify."""
        uid = connector.create_event(
            calendar_name=TEST_CALENDAR,
            summary="Date Update Test",
            start_date="2026-09-03T10:00:00",
            end_date="2026-09-03T11:00:00",
        )
        try:
            connector.update_event(
                TEST_CALENDAR, uid,
                start_date="2026-09-03T14:00:00",
                end_date="2026-09-03T15:00:00",
            )
            events = connector.get_events(TEST_CALENDAR, "2026-09-03T13:00:00", "2026-09-03T16:00:00")
            test_events = [e for e in events if e["uid"] == uid]
            assert len(test_events) == 1
            assert "2026-09-03" in test_events[0]["start_date"]
        finally:
            _delete_event_by_uid(uid)

    def test_update_multiple_fields(self, connector):
        """Update summary and location in one call."""
        uid = connector.create_event(
            calendar_name=TEST_CALENDAR,
            summary="Multi Update Test",
            start_date="2026-09-04T10:00:00",
            end_date="2026-09-04T11:00:00",
            location="Old Place",
        )
        try:
            result = connector.update_event(
                TEST_CALENDAR, uid,
                summary="New Multi Title",
                location="New Place",
            )
            assert "summary" in result["updated_fields"]
            assert "location" in result["updated_fields"]
            events = connector.get_events(TEST_CALENDAR, "2026-09-04T00:00:00", "2026-09-05T00:00:00")
            test_events = [e for e in events if e["uid"] == uid]
            assert test_events[0]["summary"] == "New Multi Title"
            assert test_events[0]["location"] == "New Place"
        finally:
            _delete_event_by_uid(uid)

    def test_update_nonexistent_event(self, connector):
        """Updating a non-existent UID should raise an error."""
        with pytest.raises(Exception, match="Event not found"):
            connector.update_event(TEST_CALENDAR, "DOES-NOT-EXIST-UID", summary="X")

    def test_clear_location(self, connector):
        """Passing location="" should clear the location field."""
        uid = connector.create_event(
            calendar_name=TEST_CALENDAR,
            summary="Clear Location Test",
            start_date="2026-09-05T10:00:00",
            end_date="2026-09-05T11:00:00",
            location="Will Be Cleared",
        )
        try:
            connector.update_event(TEST_CALENDAR, uid, location="")
            events = connector.get_events(TEST_CALENDAR, "2026-09-05T00:00:00", "2026-09-06T00:00:00")
            test_events = [e for e in events if e["uid"] == uid]
            assert len(test_events) == 1
            assert test_events[0]["location"] == ""
        finally:
            _delete_event_by_uid(uid)


class TestDeleteEventsIntegration:
    """Integration tests for delete_events against real Calendar.app."""

    def test_delete_single_event(self, connector):
        """Create event, delete it, verify it's gone via get_events."""
        uid = connector.create_event(
            calendar_name=TEST_CALENDAR,
            summary="Delete Single Test",
            start_date="2026-10-01T10:00:00",
            end_date="2026-10-01T11:00:00",
        )
        try:
            # Verify event exists
            events = connector.get_events(TEST_CALENDAR, "2026-10-01T00:00:00", "2026-10-02T00:00:00")
            assert any(e["uid"] == uid for e in events)

            # Delete it
            result = connector.delete_events(TEST_CALENDAR, uid)
            assert uid in result["deleted_uids"]
            assert result["not_found_uids"] == []

            # Verify it's gone
            events = connector.get_events(TEST_CALENDAR, "2026-10-01T00:00:00", "2026-10-02T00:00:00")
            assert not any(e["uid"] == uid for e in events)
        finally:
            _delete_event_by_uid(uid)

    def test_delete_multiple_events(self, connector):
        """Create 3 events, delete all, verify gone."""
        uids = []
        for i in range(3):
            uid = connector.create_event(
                calendar_name=TEST_CALENDAR,
                summary=f"Batch Delete Test {i}",
                start_date="2026-10-02T10:00:00",
                end_date="2026-10-02T11:00:00",
            )
            uids.append(uid)
        try:
            result = connector.delete_events(TEST_CALENDAR, uids)
            assert len(result["deleted_uids"]) == 3
            assert result["not_found_uids"] == []

            events = connector.get_events(TEST_CALENDAR, "2026-10-02T00:00:00", "2026-10-03T00:00:00")
            for uid in uids:
                assert not any(e["uid"] == uid for e in events)
        finally:
            for uid in uids:
                _delete_event_by_uid(uid)

    def test_delete_nonexistent_event(self, connector):
        """Deleting a non-existent UID should report it as not found."""
        result = connector.delete_events(TEST_CALENDAR, "DOES-NOT-EXIST-UID")
        assert result["deleted_uids"] == []
        assert "DOES-NOT-EXIST-UID" in result["not_found_uids"]

    def test_delete_already_deleted(self, connector):
        """Deleting an event twice — second attempt reports not found."""
        uid = connector.create_event(
            calendar_name=TEST_CALENDAR,
            summary="Double Delete Test",
            start_date="2026-10-03T10:00:00",
            end_date="2026-10-03T11:00:00",
        )
        try:
            result1 = connector.delete_events(TEST_CALENDAR, uid)
            assert uid in result1["deleted_uids"]

            result2 = connector.delete_events(TEST_CALENDAR, uid)
            assert result2["deleted_uids"] == []
            assert uid in result2["not_found_uids"]
        finally:
            _delete_event_by_uid(uid)
