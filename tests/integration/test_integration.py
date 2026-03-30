"""Integration tests for Apple Calendar MCP — runs against real Calendar.app.

Requires:
    - CALENDAR_TEST_MODE=true environment variable
    - The test calendar is created/deleted automatically by conftest.py

Run with: make test-integration
"""
import calendar as cal_mod
import os
import re
import time
import uuid
from datetime import date

import pytest

from apple_calendar_mcp.calendar_connector import CalendarConnector, CalendarSafetyError, run_applescript, run_swift_helper


def _future_date(year_offset: int, month: int, day: int, time: str = "") -> str:
    """Generate a future date string relative to the current year."""
    year = date.today().year + year_offset
    base = f"{year}-{month:02d}-{day:02d}"
    return f"{base}T{time}" if time else base


def _nth_weekday(year_offset: int, month: int, weekday: int, n: int) -> date:
    """Find the nth occurrence of a weekday in a month (1-indexed, negative for last).

    weekday: 0=Monday, 4=Friday (same as date.weekday())
    n: 1=first, 2=second, ..., -1=last
    """
    year = date.today().year + year_offset
    if n > 0:
        # Find first occurrence, then add (n-1) weeks
        first_day = date(year, month, 1)
        offset = (weekday - first_day.weekday()) % 7
        result = date(year, month, 1 + offset + (n - 1) * 7)
    else:
        # Last occurrence: find last day, walk back
        last_day = date(year, month, cal_mod.monthrange(year, month)[1])
        offset = (last_day.weekday() - weekday) % 7
        result = date(year, month, last_day.day - offset)
    return result


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


def _update_single_event(connector, calendar_id, event_uid, **kwargs):
    """Update a single event via update_events and return the result."""
    update = {"uid": event_uid}
    field_map = {
        "summary": "summary", "start_date": "start_date", "end_date": "end_date",
        "location": "location", "notes": "notes", "url": "url",
        "allday_event": "allday", "availability": "availability",
        "timezone": "timezone", "recurrence_rule": "recurrence",
        "occurrence_date": "occurrence_date", "span": "span",
    }
    for py_key, json_key in field_map.items():
        if py_key in kwargs and kwargs[py_key] is not None:
            value = kwargs[py_key]
            if py_key == "allday_event":
                update[json_key] = value  # already bool
                continue
            update[json_key] = value
    if "alert_minutes" in kwargs:
        update["alerts"] = kwargs["alert_minutes"]
    result = connector.update_events(calendar_id=calendar_id, updates=[update])
    if result.get("errors"):
        raise ValueError(result["errors"][0].get("error", "Unknown error"))
    return result["updated"][0] if result.get("updated") else {}


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


def _create_single_event(connector, calendar_id, summary, start_date, end_date, **kwargs):
    """Create a single event via create_events and return the UID."""
    event = {"summary": summary, "start_date": start_date, "end_date": end_date}
    if kwargs.get("location"):
        event["location"] = kwargs["location"]
    if kwargs.get("notes"):
        event["notes"] = kwargs["notes"]
    if kwargs.get("url"):
        event["url"] = kwargs["url"]
    if kwargs.get("allday_event"):
        event["allday"] = True
    if kwargs.get("recurrence_rule"):
        event["recurrence"] = kwargs["recurrence_rule"]
    if kwargs.get("alert_minutes"):
        event["alerts"] = kwargs["alert_minutes"]
    if kwargs.get("availability"):
        event["availability"] = kwargs["availability"]
    if kwargs.get("timezone"):
        event["timezone"] = kwargs["timezone"]
    result = connector.create_events(events=[event], calendar_id=calendar_id)
    return result["created"][0]["uid"]


class TestCalendarManagementIntegration:
    """Integration tests for create_calendar and delete_calendar."""

    def test_create_and_delete_calendar(self, connector):
        """Create a calendar, verify it exists, delete it, verify it's gone."""
        cal_name = "MCP-Test-Calendar-2"
        result = None
        try:
            result = connector.create_calendar(cal_name)
            assert result["name"] == cal_name

            calendars = connector.get_calendars()
            names = [c["name"] for c in calendars]
            assert cal_name in names
        finally:
            try:
                if result:
                    connector.delete_calendar(calendar_id=result["calendar_id"])
            except Exception:
                pass

        calendars = connector.get_calendars()
        names = [c["name"] for c in calendars]
        assert cal_name not in names


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
        """Each calendar should have calendar_id, name, writable, description, color, source."""
        calendars = connector.get_calendars()
        for cal in calendars:
            assert "calendar_id" in cal, f"Missing 'calendar_id' in calendar: {cal}"
            assert "name" in cal, f"Missing 'name' in calendar: {cal}"
            assert "writable" in cal, f"Missing 'writable' in calendar: {cal}"
            assert "description" in cal, f"Missing 'description' in calendar: {cal}"
            assert "color" in cal, f"Missing 'color' in calendar: {cal}"
            assert "source" in cal, f"Missing 'source' in calendar: {cal}"

    def test_calendar_id_is_uuid_string(self, connector):
        """calendar_id should be a non-empty string (UUID format)."""
        calendars = connector.get_calendars()
        for cal in calendars:
            assert isinstance(cal["calendar_id"], str)
            assert len(cal["calendar_id"]) > 0, f"Empty calendar_id for {cal['name']}"

    def test_get_events_by_calendar_id(self, connector):
        """Events can be queried by calendar_id instead of name."""
        calendars = connector.get_calendars()
        test_cal = next(c for c in calendars if c["name"] == TEST_CALENDAR)
        cal_id = test_cal["calendar_id"]
        # Query by ID should work the same as by name
        events_by_id = connector.get_events(
            start_date=_future_date(3, 1, 1),
            end_date=_future_date(3, 12, 31),
            calendar_ids=[cal_id],
        )
        assert isinstance(events_by_id, list)

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


class TestCreateEventsIntegration:
    """Integration tests for create_events against real Calendar.app."""

    def test_creates_event_and_returns_uid(self, connector, test_calendar_id):
        """Creating an event should return a valid UID string."""
        uid = _create_single_event(connector,
            calendar_id=test_calendar_id,
            summary="Integration Test Event",
            start_date=_future_date(3, 6, 15, "10:00:00"),
            end_date=_future_date(3, 6, 15, "11:00:00"),
        )
        try:
            assert isinstance(uid, str)
            assert len(uid) > 0
            assert re.match(r"^[A-F0-9-]+$", uid, re.IGNORECASE), f"UID doesn't look like UUID: {uid}"
        finally:
            _delete_event_by_uid(uid)

    def test_created_event_has_correct_summary(self, connector, test_calendar_id):
        """Verify the created event has the right summary via AppleScript query."""
        uid = _create_single_event(connector,
            calendar_id=test_calendar_id,
            summary="Verify Summary Test",
            start_date=_future_date(3, 6, 15, "14:00:00"),
            end_date=_future_date(3, 6, 15, "15:00:00"),
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

    def test_creates_event_with_optional_fields(self, connector, test_calendar_id):
        """Creating an event with location, notes, and URL should succeed."""
        uid = _create_single_event(connector,
            calendar_id=test_calendar_id,
            summary="Full Event Test",
            start_date=_future_date(3, 6, 15, "09:00:00"),
            end_date=_future_date(3, 6, 15, "10:00:00"),
            location="Conference Room B",
            notes="Test description with details",
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

    def test_creates_allday_event(self, connector, test_calendar_id):
        """Creating an all-day event should set the allday flag."""
        uid = _create_single_event(connector,
            calendar_id=test_calendar_id,
            summary="All Day Test",
            start_date=_future_date(3, 6, 15),
            end_date=_future_date(3, 6, 15),
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

    def test_batch_creates_multiple_events(self, connector, test_calendar_id):
        """Batch create should handle multiple events in one call."""
        events = [
            {"summary": "Batch Event 1", "start_date": _future_date(3, 6, 20, "10:00:00"), "end_date": _future_date(3, 6, 20, "11:00:00")},
            {"summary": "Batch Event 2", "start_date": _future_date(3, 6, 20, "14:00:00"), "end_date": _future_date(3, 6, 20, "15:00:00")},
        ]
        result = connector.create_events(events=events, calendar_id=test_calendar_id)
        uids = [c["uid"] for c in result["created"]]
        try:
            assert len(result["created"]) == 2
            assert result["errors"] == []
            assert result["created"][0]["summary"] == "Batch Event 1"
            assert result["created"][1]["summary"] == "Batch Event 2"
        finally:
            for uid in uids:
                _delete_event_by_uid(uid)


class TestGetEventsIntegration:
    """Integration tests for get_events against real Calendar.app via EventKit."""

    def test_get_events_returns_created_event(self, connector, test_calendar_id):
        """Create an event, then verify get_events returns it."""
        uid = _create_single_event(connector,
            calendar_id=test_calendar_id,
            summary="GetEvents Test",
            start_date=_future_date(3, 7, 1, "10:00:00"),
            end_date=_future_date(3, 7, 1, "11:00:00"),
        )
        try:
            events = connector.get_events(
                start_date=_future_date(3, 7, 1, "00:00:00"),
                end_date=_future_date(3, 7, 2, "00:00:00"),
                calendar_ids=[test_calendar_id],
            )
            summaries = [e["summary"] for e in events]
            assert "GetEvents Test" in summaries
        finally:
            _delete_event_by_uid(uid)

    def test_date_range_filtering(self, connector, test_calendar_id):
        """Event outside date range should not be returned."""
        uid = _create_single_event(connector,
            calendar_id=test_calendar_id,
            summary="Outside Range Test",
            start_date=_future_date(3, 8, 1, "10:00:00"),
            end_date=_future_date(3, 8, 1, "11:00:00"),
        )
        try:
            events = connector.get_events(
                start_date=_future_date(3, 7, 1, "00:00:00"),
                end_date=_future_date(3, 7, 2, "00:00:00"),
                calendar_ids=[test_calendar_id],
            )
            summaries = [e["summary"] for e in events]
            assert "Outside Range Test" not in summaries
        finally:
            _delete_event_by_uid(uid)

    def test_event_has_expected_keys(self, connector, test_calendar_id):
        """Returned event dicts should have all expected keys."""
        uid = _create_single_event(connector,
            calendar_id=test_calendar_id,
            summary="Keys Test Event",
            start_date=_future_date(3, 7, 2, "10:00:00"),
            end_date=_future_date(3, 7, 2, "11:00:00"),
            location="Test Location",
        )
        try:
            events = connector.get_events(
                start_date=_future_date(3, 7, 2, "00:00:00"),
                end_date=_future_date(3, 7, 3, "00:00:00"),
                calendar_ids=[test_calendar_id],
            )
            test_events = [e for e in events if e["summary"] == "Keys Test Event"]
            assert len(test_events) == 1
            event = test_events[0]
            for key in ["uid", "summary", "start_date", "end_date", "allday_event",
                         "location", "notes", "url", "status", "calendar_name"]:
                assert key in event, f"Missing key '{key}' in event"
            assert event["location"] == "Test Location"
            assert event["calendar_name"] == TEST_CALENDAR
        finally:
            _delete_event_by_uid(uid)

    def test_empty_date_range_returns_empty_list(self, connector, test_calendar_id):
        """Date range with no events should return empty list."""
        events = connector.get_events(
            start_date="2099-01-01T00:00:00",
            end_date="2099-01-02T00:00:00",
            calendar_ids=[test_calendar_id],
        )
        assert events == []

    def test_get_events_year_boundary(self, connector, test_calendar_id):
        """Query spanning Dec 29 – Jan 3 should return events on both sides of year boundary."""
        uid_dec = _create_single_event(connector,
            calendar_id=test_calendar_id,
            summary="Year Boundary Dec 31",
            start_date="2029-12-31T10:00:00",
            end_date="2029-12-31T11:00:00",
        )
        uid_jan = _create_single_event(connector,
            calendar_id=test_calendar_id,
            summary="Year Boundary Jan 2",
            start_date="2030-01-02T10:00:00",
            end_date="2030-01-02T11:00:00",
        )
        try:
            events = connector.get_events(
                start_date="2029-12-29",
                end_date="2030-01-04",
                calendar_ids=[test_calendar_id],
            )
            uids = [e["uid"] for e in events]
            assert uid_dec in uids, "Dec 31 event not found in year-boundary query"
            assert uid_jan in uids, "Jan 2 event not found in year-boundary query"
        finally:
            _delete_event_by_uid(uid_dec)
            _delete_event_by_uid(uid_jan)


class TestUpdateEventIntegration:
    """Integration tests for update_events against real Calendar.app."""

    def test_update_summary(self, connector, test_calendar_id):
        """Update summary and verify via get_events."""
        uid = _create_single_event(connector,
            calendar_id=test_calendar_id,
            summary="Original Summary",
            start_date=_future_date(3, 9, 1, "10:00:00"),
            end_date=_future_date(3, 9, 1, "11:00:00"),
        )
        try:
            _update_single_event(connector, test_calendar_id, uid, summary="Updated Summary")
            events = connector.get_events(start_date=_future_date(3, 9, 1, "00:00:00"), end_date=_future_date(3, 9, 2, "00:00:00"), calendar_ids=[test_calendar_id])
            test_events = [e for e in events if e["uid"] == uid]
            assert len(test_events) == 1
            assert test_events[0]["summary"] == "Updated Summary"
        finally:
            _delete_event_by_uid(uid)

    def test_update_location(self, connector, test_calendar_id):
        """Update location from A to B and verify."""
        uid = _create_single_event(connector,
            calendar_id=test_calendar_id,
            summary="Location Update Test",
            start_date=_future_date(3, 9, 2, "10:00:00"),
            end_date=_future_date(3, 9, 2, "11:00:00"),
            location="Room A",
        )
        try:
            _update_single_event(connector, test_calendar_id, uid, location="Room B")
            events = connector.get_events(start_date=_future_date(3, 9, 2, "00:00:00"), end_date=_future_date(3, 9, 3, "00:00:00"), calendar_ids=[test_calendar_id])
            test_events = [e for e in events if e["uid"] == uid]
            assert len(test_events) == 1
            assert test_events[0]["location"] == "Room B"
        finally:
            _delete_event_by_uid(uid)

    def test_update_dates(self, connector, test_calendar_id):
        """Update start/end dates and verify."""
        uid = _create_single_event(connector,
            calendar_id=test_calendar_id,
            summary="Date Update Test",
            start_date=_future_date(3, 9, 3, "10:00:00"),
            end_date=_future_date(3, 9, 3, "11:00:00"),
        )
        try:
            _update_single_event(connector, test_calendar_id, uid,
                start_date=_future_date(3, 9, 3, "14:00:00"),
                end_date=_future_date(3, 9, 3, "15:00:00"),
            )
            events = connector.get_events(start_date=_future_date(3, 9, 3, "13:00:00"), end_date=_future_date(3, 9, 3, "16:00:00"), calendar_ids=[test_calendar_id])
            test_events = [e for e in events if e["uid"] == uid]
            assert len(test_events) == 1
            assert _future_date(3, 9, 3) in test_events[0]["start_date"]
        finally:
            _delete_event_by_uid(uid)

    def test_update_multiple_fields(self, connector, test_calendar_id):
        """Update summary and location in one call."""
        uid = _create_single_event(connector,
            calendar_id=test_calendar_id,
            summary="Multi Update Test",
            start_date=_future_date(3, 9, 4, "10:00:00"),
            end_date=_future_date(3, 9, 4, "11:00:00"),
            location="Old Place",
        )
        try:
            result = _update_single_event(connector, test_calendar_id, uid,
                summary="New Multi Title",
                location="New Place",
            )
            assert "summary" in result.get("updated_fields", [])
            assert "location" in result.get("updated_fields", [])
            events = connector.get_events(start_date=_future_date(3, 9, 4, "00:00:00"), end_date=_future_date(3, 9, 5, "00:00:00"), calendar_ids=[test_calendar_id])
            test_events = [e for e in events if e["uid"] == uid]
            assert test_events[0]["summary"] == "New Multi Title"
            assert test_events[0]["location"] == "New Place"
        finally:
            _delete_event_by_uid(uid)

    def test_update_nonexistent_event(self, connector, test_calendar_id):
        """Updating a non-existent UID should raise an error."""
        with pytest.raises(ValueError, match="Event not found"):
            _update_single_event(connector, test_calendar_id, "DOES-NOT-EXIST-UID", summary="X")

    def test_clear_location(self, connector, test_calendar_id):
        """Passing location="" should clear the location field."""
        uid = _create_single_event(connector,
            calendar_id=test_calendar_id,
            summary="Clear Location Test",
            start_date=_future_date(3, 9, 5, "10:00:00"),
            end_date=_future_date(3, 9, 5, "11:00:00"),
            location="Will Be Cleared",
        )
        try:
            _update_single_event(connector, test_calendar_id, uid, location="")
            events = connector.get_events(start_date=_future_date(3, 9, 5, "00:00:00"), end_date=_future_date(3, 9, 6, "00:00:00"), calendar_ids=[test_calendar_id])
            test_events = [e for e in events if e["uid"] == uid]
            assert len(test_events) == 1
            assert test_events[0]["location"] == ""
        finally:
            _delete_event_by_uid(uid)

    def test_update_title_only(self, connector, test_calendar_id):
        """Updating only summary should leave location and notes unchanged."""
        uid = _create_single_event(connector,
            calendar_id=test_calendar_id,
            summary="Original Title",
            start_date=_future_date(4, 9, 10, "10:00:00"),
            end_date=_future_date(4, 9, 10, "11:00:00"),
            location="Keep This Location",
            notes="Keep these notes",
        )
        try:
            _update_single_event(connector, test_calendar_id, uid, summary="New Title")
            events = connector.get_events(start_date=_future_date(4, 9, 10), end_date=_future_date(4, 9, 11), calendar_ids=[test_calendar_id])
            matches = [e for e in events if e["uid"] == uid]
            assert len(matches) == 1
            assert matches[0]["summary"] == "New Title"
            assert matches[0]["location"] == "Keep This Location"
            assert matches[0]["notes"] == "Keep these notes"
        finally:
            _delete_event_by_uid(uid)

    def test_update_allday_event_notes_preserves_fields(self, connector, test_calendar_id):
        """Updating notes on an all-day event should preserve location and all-day status."""
        uid = _create_single_event(connector,
            calendar_id=test_calendar_id,
            summary="All Day Update Test",
            start_date=_future_date(4, 9, 15),
            end_date=_future_date(4, 9, 15),
            allday_event=True,
            location="Conference Room",
            notes="Original notes",
        )
        try:
            _update_single_event(connector, test_calendar_id, uid, notes="Updated notes")
            events = connector.get_events(start_date=_future_date(4, 9, 15), end_date=_future_date(4, 9, 17), calendar_ids=[test_calendar_id])
            matches = [e for e in events if e["uid"] == uid]
            assert len(matches) == 1
            assert matches[0]["notes"] == "Updated notes"
            assert matches[0]["location"] == "Conference Room"
            assert matches[0]["allday_event"] is True
        finally:
            _delete_event_by_uid(uid)

    def test_reschedule_event_to_different_day(self, connector, test_calendar_id):
        """Moving an event to a different day should update dates and preserve other fields."""
        uid = _create_single_event(connector,
            calendar_id=test_calendar_id,
            summary="Reschedule Day Test",
            start_date=_future_date(4, 9, 20, "10:00:00"),
            end_date=_future_date(4, 9, 20, "11:00:00"),
            location="Room B",
            notes="Important meeting",
        )
        try:
            _update_single_event(connector, test_calendar_id, uid,
                start_date=_future_date(4, 9, 25, "14:00:00"),
                end_date=_future_date(4, 9, 25, "15:00:00"),
            )
            # Query the new date range
            events = connector.get_events(start_date=_future_date(4, 9, 25), end_date=_future_date(4, 9, 26), calendar_ids=[test_calendar_id])
            matches = [e for e in events if e["uid"] == uid]
            assert len(matches) == 1
            assert _future_date(4, 9, 25) in matches[0]["start_date"]
            assert "14:00" in matches[0]["start_date"]
            assert matches[0]["location"] == "Room B"
            assert matches[0]["notes"] == "Important meeting"

            # Verify not at original date
            old_events = connector.get_events(start_date=_future_date(4, 9, 20), end_date=_future_date(4, 9, 21), calendar_ids=[test_calendar_id])
            assert not any(e["uid"] == uid for e in old_events)
        finally:
            _delete_event_by_uid(uid)

    def test_clear_notes(self, connector, test_calendar_id):
        """Passing notes='' should empty the notes field."""
        uid = _create_single_event(connector,
            calendar_id=test_calendar_id,
            summary="Clear Notes Test",
            start_date=_future_date(5, 4, 10, "10:00:00"),
            end_date=_future_date(5, 4, 10, "11:00:00"),
            notes="These notes will be cleared",
        )
        try:
            connector.update_events(calendar_id=test_calendar_id, updates=[{"uid": uid, "notes": ""}])
            events = connector.get_events(start_date=_future_date(5, 4, 10, "00:00:00"), end_date=_future_date(5, 4, 11, "00:00:00"), calendar_ids=[test_calendar_id])
            matches = [e for e in events if e["uid"] == uid]
            assert len(matches) == 1
            assert matches[0].get("notes", "") == ""
        finally:
            _delete_event_by_uid(uid)

    def test_clear_url(self, connector, test_calendar_id):
        """Passing url='' should empty the url field."""
        uid = _create_single_event(connector,
            calendar_id=test_calendar_id,
            summary="Clear URL Test",
            start_date=_future_date(5, 4, 11, "10:00:00"),
            end_date=_future_date(5, 4, 11, "11:00:00"),
            url="https://example.com/will-be-cleared",
        )
        try:
            connector.update_events(calendar_id=test_calendar_id, updates=[{"uid": uid, "url": ""}])
            events = connector.get_events(start_date=_future_date(5, 4, 11, "00:00:00"), end_date=_future_date(5, 4, 12, "00:00:00"), calendar_ids=[test_calendar_id])
            matches = [e for e in events if e["uid"] == uid]
            assert len(matches) == 1
            assert matches[0].get("url", "") == ""
        finally:
            _delete_event_by_uid(uid)

    def test_clear_alerts(self, connector, test_calendar_id):
        """Clearing alerts via clear_alerts=True should remove all alerts."""
        uid = _create_single_event(connector,
            calendar_id=test_calendar_id,
            summary="Clear Alerts Test",
            start_date=_future_date(5, 4, 12, "10:00:00"),
            end_date=_future_date(5, 4, 12, "11:00:00"),
            alert_minutes=[15, 60],
        )
        try:
            _update_single_event(connector, test_calendar_id, uid, alert_minutes=[])
            events = connector.get_events(start_date=_future_date(5, 4, 12, "00:00:00"), end_date=_future_date(5, 4, 13, "00:00:00"), calendar_ids=[test_calendar_id])
            matches = [e for e in events if e["uid"] == uid]
            assert len(matches) == 1
            assert matches[0].get("alerts", []) == []
        finally:
            _delete_event_by_uid(uid)

    def test_update_availability(self, connector, test_calendar_id):
        """Updating availability to 'free' should be readable back."""
        uid = _create_single_event(connector,
            calendar_id=test_calendar_id,
            summary="Availability Update Test",
            start_date=_future_date(5, 4, 13, "10:00:00"),
            end_date=_future_date(5, 4, 13, "11:00:00"),
        )
        try:
            _update_single_event(connector, test_calendar_id, uid, availability="free")
            events = connector.get_events(start_date=_future_date(5, 4, 13, "00:00:00"), end_date=_future_date(5, 4, 14, "00:00:00"), calendar_ids=[test_calendar_id])
            matches = [e for e in events if e["uid"] == uid]
            assert len(matches) == 1
            assert matches[0].get("availability") == "free"
        finally:
            _delete_event_by_uid(uid)


class TestDeleteEventsIntegration:
    """Integration tests for delete_events against real Calendar.app."""

    def test_delete_single_event(self, connector, test_calendar_id):
        """Create event, delete it, verify it's gone via get_events."""
        uid = _create_single_event(connector,
            calendar_id=test_calendar_id,
            summary="Delete Single Test",
            start_date=_future_date(3, 10, 1, "10:00:00"),
            end_date=_future_date(3, 10, 1, "11:00:00"),
        )
        try:
            # Verify event exists
            events = connector.get_events(start_date=_future_date(3, 10, 1, "00:00:00"), end_date=_future_date(3, 10, 2, "00:00:00"), calendar_ids=[test_calendar_id])
            assert any(e["uid"] == uid for e in events)

            # Delete it
            result = connector.delete_events(calendar_id=test_calendar_id, event_uids=uid)
            assert uid in result["deleted_uids"]
            assert result["not_found_uids"] == []

            # Verify it's gone
            events = connector.get_events(start_date=_future_date(3, 10, 1, "00:00:00"), end_date=_future_date(3, 10, 2, "00:00:00"), calendar_ids=[test_calendar_id])
            assert not any(e["uid"] == uid for e in events)
        finally:
            _delete_event_by_uid(uid)

    def test_delete_multiple_events(self, connector, test_calendar_id):
        """Create 3 events, delete all, verify gone."""
        uids = []
        for i in range(3):
            uid = _create_single_event(connector,
                calendar_id=test_calendar_id,
                summary=f"Batch Delete Test {i}",
                start_date=_future_date(3, 10, 2, "10:00:00"),
                end_date=_future_date(3, 10, 2, "11:00:00"),
            )
            uids.append(uid)
        try:
            result = connector.delete_events(calendar_id=test_calendar_id, event_uids=uids)
            assert len(result["deleted_uids"]) == 3
            assert result["not_found_uids"] == []

            events = connector.get_events(start_date=_future_date(3, 10, 2, "00:00:00"), end_date=_future_date(3, 10, 3, "00:00:00"), calendar_ids=[test_calendar_id])
            for uid in uids:
                assert not any(e["uid"] == uid for e in events)
        finally:
            for uid in uids:
                _delete_event_by_uid(uid)

    def test_delete_nonexistent_event(self, connector, test_calendar_id):
        """Deleting a non-existent UID should report it as not found."""
        result = connector.delete_events(calendar_id=test_calendar_id, event_uids="DOES-NOT-EXIST-UID")
        assert result["deleted_uids"] == []
        assert "DOES-NOT-EXIST-UID" in result["not_found_uids"]

    def test_delete_already_deleted(self, connector, test_calendar_id):
        """Deleting an event twice — second attempt reports not found."""
        uid = _create_single_event(connector,
            calendar_id=test_calendar_id,
            summary="Double Delete Test",
            start_date=_future_date(3, 10, 3, "10:00:00"),
            end_date=_future_date(3, 10, 3, "11:00:00"),
        )
        try:
            result1 = connector.delete_events(calendar_id=test_calendar_id, event_uids=uid)
            assert uid in result1["deleted_uids"]

            result2 = connector.delete_events(calendar_id=test_calendar_id, event_uids=uid)
            assert result2["deleted_uids"] == []
            assert uid in result2["not_found_uids"]
        finally:
            _delete_event_by_uid(uid)

    def test_delete_single_occurrence_of_recurring(self, connector, fresh_calendar):
        """Delete one occurrence of a recurring event, verify others preserved (#84)."""
        uid = _create_single_event(connector,
            calendar_id=fresh_calendar,
            summary="Delete Occurrence Test",
            start_date=_future_date(5, 8, 7, "10:00:00"),
            end_date=_future_date(5, 8, 7, "11:00:00"),
            recurrence_rule="FREQ=WEEKLY;COUNT=3",
        )
        # Verify 3 occurrences: Aug 7, 14, 21
        events = connector.get_events(start_date=_future_date(5, 8, 1), end_date=_future_date(5, 8, 31), calendar_ids=[fresh_calendar])
        series = [e for e in events if e["uid"] == uid]
        assert len(series) == 3

        # Delete the middle occurrence (Aug 14)
        result = connector.delete_events(
            calendar_id=fresh_calendar, event_uids=uid,
            span="this_event",
            occurrence_date=_future_date(5, 8, 14, "10:00:00"),
        )
        assert uid in result["deleted_uids"]

        # Verify 2 remaining occurrences (Aug 7 and 21)
        events = connector.get_events(start_date=_future_date(5, 8, 1), end_date=_future_date(5, 8, 31), calendar_ids=[fresh_calendar])
        remaining = [e for e in events if e["uid"] == uid]
        assert len(remaining) == 2, f"Expected 2 occurrences after deleting one, got {len(remaining)}"
        dates = sorted([e["start_date"][:10] for e in remaining])
        assert _future_date(5, 8, 14) not in dates, "Deleted occurrence should be gone"

    def test_delete_non_recurring_event_then_verify_absent(self, connector, test_calendar_id):
        """Delete a non-recurring event and verify it's absent via re-query (round-trip)."""
        uid = _create_single_event(connector,
            calendar_id=test_calendar_id,
            summary="Delete Verify Test",
            start_date=_future_date(4, 10, 10, "10:00:00"),
            end_date=_future_date(4, 10, 10, "11:00:00"),
        )
        # Verify it exists
        events = connector.get_events(start_date=_future_date(4, 10, 10), end_date=_future_date(4, 10, 11), calendar_ids=[test_calendar_id])
        assert any(e["uid"] == uid for e in events), "Event should exist before deletion"

        # Delete it
        result = connector.delete_events(calendar_id=test_calendar_id, event_uids=uid)
        assert uid in result["deleted_uids"]

        # Verify absent via re-query
        events = connector.get_events(start_date=_future_date(4, 10, 10), end_date=_future_date(4, 10, 11), calendar_ids=[test_calendar_id])
        assert not any(e["uid"] == uid for e in events), "Event should be absent after deletion"

    def test_delete_recurring_series_with_future_events(self, connector, fresh_calendar):
        """Delete a recurring series using span=future_events (#84)."""
        uid = _create_single_event(connector,
            calendar_id=fresh_calendar,
            summary="Delete Series Test",
            start_date=_future_date(5, 9, 2, "10:00:00"),
            end_date=_future_date(5, 9, 2, "11:00:00"),
            recurrence_rule="FREQ=WEEKLY;COUNT=4",
        )
        events = connector.get_events(start_date=_future_date(5, 9, 1), end_date=_future_date(5, 9, 30), calendar_ids=[fresh_calendar])
        series = [e for e in events if e["uid"] == uid]
        assert len(series) == 4

        # Delete entire series
        result = connector.delete_events(calendar_id=fresh_calendar, event_uids=uid, span="future_events")
        assert uid in result["deleted_uids"]

        # Verify all gone
        events = connector.get_events(start_date=_future_date(5, 9, 1), end_date=_future_date(5, 9, 30), calendar_ids=[fresh_calendar])
        remaining = [e for e in events if e["uid"] == uid]
        assert len(remaining) == 0, f"Expected 0 occurrences after deleting series, got {len(remaining)}"


class TestGetAvailabilityIntegration:
    """Integration tests for get_availability against real Calendar.app."""

    def test_free_slots_around_event(self, connector, test_calendar_id):
        """Create an event and verify free slots before and after it."""
        uid = _create_single_event(connector,
            calendar_id=test_calendar_id,
            summary="Availability Test",
            start_date=_future_date(3, 11, 1, "10:00:00"),
            end_date=_future_date(3, 11, 1, "11:00:00"),
        )
        try:
            slots = connector.get_availability(
                start_date=_future_date(3, 11, 1, "09:00:00"),
                end_date=_future_date(3, 11, 1, "12:00:00"),
                calendar_ids=[test_calendar_id],
            )
            assert len(slots) == 2
            assert slots[0]["end_date"] == _future_date(3, 11, 1, "10:00:00")
            assert slots[1]["start_date"] == _future_date(3, 11, 1, "11:00:00")
        finally:
            _delete_event_by_uid(uid)

    def test_no_events_entire_range_free(self, connector, test_calendar_id):
        """Empty date range should return single free slot."""
        slots = connector.get_availability(
            start_date="2099-06-01T09:00:00",
            end_date="2099-06-01T17:00:00",
            calendar_ids=[test_calendar_id],
        )
        assert len(slots) == 1
        assert slots[0]["duration_minutes"] == 480

    def test_min_duration_filters_short_slots(self, connector, test_calendar_id):
        """Create event leaving short gaps, verify min_duration filters them."""
        uid = _create_single_event(connector,
            calendar_id=test_calendar_id,
            summary="Availability Filter Test",
            start_date="2099-07-01T09:20:00",
            end_date="2099-07-01T10:00:00",
        )
        try:
            # Without filter: 9:00-9:20 (20m) and 10:00-12:00 (120m)
            all_slots = connector.get_availability(
                start_date="2099-07-01T09:00:00",
                end_date="2099-07-01T12:00:00",
                calendar_ids=[test_calendar_id],
            )
            assert len(all_slots) == 2

            # With filter: only 10:00-12:00 (120m) passes
            filtered = connector.get_availability(
                start_date="2099-07-01T09:00:00",
                end_date="2099-07-01T12:00:00",
                calendar_ids=[test_calendar_id],
                min_duration_minutes=30,
            )
            assert len(filtered) == 1
            assert filtered[0]["start_date"] == "2099-07-01T10:00:00"
            assert filtered[0]["duration_minutes"] == 120
        finally:
            _delete_event_by_uid(uid)

    def test_working_hours_clips_range(self, connector, test_calendar_id):
        """Working hours clip free slots to the specified window."""
        slots = connector.get_availability(
            start_date="2099-08-01T00:00:00",
            end_date="2099-08-02T00:00:00",
            calendar_ids=[test_calendar_id],
            working_hours_start="09:00",
            working_hours_end="17:00",
        )
        assert len(slots) == 1
        assert slots[0]["start_date"] == "2099-08-01T09:00:00"
        assert slots[0]["end_date"] == "2099-08-01T17:00:00"
        assert slots[0]["duration_minutes"] == 480

    def test_multi_calendar_availability(self, connector, test_calendar_id):
        """Events on different calendars should both block availability when queried together."""
        from tests.helpers.calendar_setup import create_test_calendar, delete_test_calendar

        cal2 = "MCP-Test-Calendar-2"
        create_test_calendar(cal2)
        uid1 = None
        uid2 = None
        try:
            # Look up cal2's ID
            connector_no_safety = CalendarConnector(enable_safety_checks=False)
            calendars = connector_no_safety.get_calendars()
            cal2_obj = next(c for c in calendars if c["name"] == cal2)
            cal2_id = cal2_obj["calendar_id"]

            # Event on primary calendar at 10:00-11:00
            uid1 = _create_single_event(connector,
                calendar_id=test_calendar_id,
                summary="Multi-Cal Avail A",
                start_date="2099-09-01T10:00:00",
                end_date="2099-09-01T11:00:00",
            )
            # Event on second calendar at 14:00-15:00
            result = connector_no_safety.create_events(events=[
                {"summary": "Multi-Cal Avail B", "start_date": "2099-09-01T14:00:00", "end_date": "2099-09-01T15:00:00"},
            ], calendar_id=cal2_id)
            uid2 = result["created"][0]["uid"]

            # Query availability across both calendars
            slots = connector.get_availability(
                start_date="2099-09-01T09:00:00",
                end_date="2099-09-01T17:00:00",
                calendar_ids=[test_calendar_id, cal2_id],
            )
            # Both events should block, leaving 3 free slots:
            # 09:00-10:00, 11:00-14:00, 15:00-17:00
            assert len(slots) == 3
            assert slots[0]["start_date"] == "2099-09-01T09:00:00"
            assert slots[0]["end_date"] == "2099-09-01T10:00:00"
            assert slots[1]["start_date"] == "2099-09-01T11:00:00"
            assert slots[1]["end_date"] == "2099-09-01T14:00:00"
            assert slots[2]["start_date"] == "2099-09-01T15:00:00"
            assert slots[2]["end_date"] == "2099-09-01T17:00:00"
        finally:
            if uid1:
                _delete_event_by_uid(uid1)
            try:
                delete_test_calendar(cal2)
            except Exception:
                pass


class TestRecurringEventsIntegration:
    """Integration tests for recurring event handling."""

    def test_create_recurring_event_and_read_occurrences(self, connector, fresh_calendar):
        """Create a recurring event, verify multiple occurrences returned with recurrence fields."""
        uid = _create_single_event(connector,
            calendar_id=fresh_calendar,
            summary="Recurring Test",
            start_date=_future_date(4, 1, 5, "10:00:00"),
            end_date=_future_date(4, 1, 5, "11:00:00"),
            recurrence_rule="FREQ=WEEKLY;COUNT=3",
        )
        events = connector.get_events(
            start_date=_future_date(4, 1, 1),
            end_date=_future_date(4, 1, 31),
            calendar_ids=[fresh_calendar],
        )
        recurring = [e for e in events if e["uid"] == uid]
        assert len(recurring) == 3

        # All share the same UID
        assert all(e["uid"] == uid for e in recurring)

        # All have recurrence fields
        for evt in recurring:
            assert evt["is_recurring"] is True
            assert "FREQ=WEEKLY" in evt["recurrence"]
            assert evt["is_detached"] is False

        # Each has a different occurrence_date
        occ_dates = [e["occurrence_date"] for e in recurring]
        assert len(set(occ_dates)) == 3

    def test_monthly_nth_weekday_recurrence(self, connector, fresh_calendar):
        """Create monthly event on 4th Monday — verify correct dates (#79)."""
        jan_4th_mon = _nth_weekday(5, 1, 0, 4)  # 4th Monday of Jan
        uid = _create_single_event(connector,
            calendar_id=fresh_calendar,
            summary="4th Monday Test",
            start_date=f"{jan_4th_mon.isoformat()}T10:00:00",
            end_date=f"{jan_4th_mon.isoformat()}T11:00:00",
            recurrence_rule="FREQ=MONTHLY;BYDAY=4MO;COUNT=3",
        )
        events = connector.get_events(
            start_date=_future_date(5, 1, 1),
            end_date=_future_date(5, 4, 30),
            calendar_ids=[fresh_calendar],
        )
        recurring = [e for e in events if e["uid"] == uid]
        assert len(recurring) == 3, f"Expected 3 occurrences, got {len(recurring)}"

        # Verify dates are all 4th Mondays
        feb_4th_mon = _nth_weekday(5, 2, 0, 4)
        mar_4th_mon = _nth_weekday(5, 3, 0, 4)
        dates = sorted([e["start_date"][:10] for e in recurring])
        assert dates[0] == jan_4th_mon.isoformat()
        assert dates[1] == feb_4th_mon.isoformat()
        assert dates[2] == mar_4th_mon.isoformat()

    def test_recurrence_with_until_end_date(self, connector, fresh_calendar):
        """Create weekly event with UNTIL — verify recurrence stops (#81)."""
        uid = _create_single_event(connector,
            calendar_id=fresh_calendar,
            summary="Until Test",
            start_date=_future_date(5, 3, 1, "10:00:00"),
            end_date=_future_date(5, 3, 1, "11:00:00"),
            recurrence_rule=f"FREQ=WEEKLY;UNTIL={date.today().year + 5}0322T000000",
        )
        events = connector.get_events(
            start_date=_future_date(5, 3, 1),
            end_date=_future_date(5, 4, 30),
            calendar_ids=[fresh_calendar],
        )
        recurring = [e for e in events if e["uid"] == uid]
        # Should have ~3 occurrences (Mar 1, 8, 15) — Mar 22 is the UNTIL date
        assert len(recurring) <= 4, f"Should stop by March 22, got {len(recurring)} occurrences"
        assert len(recurring) >= 3, f"Should have at least 3 occurrences, got {len(recurring)}"

        # No occurrence should be on or after March 22
        for e in recurring:
            assert e["start_date"][:10] < _future_date(5, 3, 22), (
                f"Occurrence {e['start_date']} should be before UNTIL date {_future_date(5, 3, 22)}"
            )

    def test_last_friday_recurrence(self, connector, fresh_calendar):
        """Create monthly event on last Friday (BYDAY=-1FR) — verify correct dates (#79)."""
        jan_last_fri = _nth_weekday(5, 1, 4, -1)  # Last Friday of Jan
        uid = _create_single_event(connector,
            calendar_id=fresh_calendar,
            summary="Last Friday Test",
            start_date=f"{jan_last_fri.isoformat()}T10:00:00",
            end_date=f"{jan_last_fri.isoformat()}T11:00:00",
            recurrence_rule="FREQ=MONTHLY;BYDAY=-1FR;COUNT=3",
        )
        events = connector.get_events(
            start_date=_future_date(5, 1, 1),
            end_date=_future_date(5, 4, 30),
            calendar_ids=[fresh_calendar],
        )
        recurring = [e for e in events if e["uid"] == uid]
        assert len(recurring) == 3, f"Expected 3 occurrences, got {len(recurring)}"

        feb_last_fri = _nth_weekday(5, 2, 4, -1)
        mar_last_fri = _nth_weekday(5, 3, 4, -1)
        dates = sorted([e["start_date"][:10] for e in recurring])
        assert dates[0] == jan_last_fri.isoformat()
        assert dates[1] == feb_last_fri.isoformat()
        assert dates[2] == mar_last_fri.isoformat()

    def test_add_recurrence_to_existing_event(self, connector, fresh_calendar):
        """Create non-recurring event, add recurrence via update (#80)."""
        uid = _create_single_event(connector,
            calendar_id=fresh_calendar,
            summary="Add Recurrence Test",
            start_date=_future_date(5, 4, 3, "10:00:00"),
            end_date=_future_date(5, 4, 3, "11:00:00"),
        )
        # Verify starts as non-recurring
        events = connector.get_events(start_date=_future_date(5, 4, 1), end_date=_future_date(5, 4, 30), calendar_ids=[fresh_calendar])
        matches = [e for e in events if e["uid"] == uid]
        assert len(matches) == 1
        assert matches[0]["is_recurring"] is False

        # Add weekly recurrence
        _update_single_event(connector, fresh_calendar, uid, recurrence_rule="FREQ=WEEKLY;COUNT=3")

        # Verify now has 3 occurrences
        events = connector.get_events(start_date=_future_date(5, 4, 1), end_date=_future_date(5, 4, 30), calendar_ids=[fresh_calendar])
        matches = [e for e in events if e["uid"] == uid]
        assert len(matches) == 3, f"Expected 3 occurrences, got {len(matches)}"
        assert all(e["is_recurring"] for e in matches)

    def test_remove_recurrence_from_event(self, connector, fresh_calendar):
        """Create recurring event, remove recurrence via update (#80)."""
        uid = _create_single_event(connector,
            calendar_id=fresh_calendar,
            summary="Remove Recurrence Test",
            start_date=_future_date(5, 5, 1, "10:00:00"),
            end_date=_future_date(5, 5, 1, "11:00:00"),
            recurrence_rule="FREQ=WEEKLY;COUNT=4",
        )
        # Verify starts with 4 occurrences
        events = connector.get_events(start_date=_future_date(5, 5, 1), end_date=_future_date(5, 5, 31), calendar_ids=[fresh_calendar])
        matches = [e for e in events if e["uid"] == uid]
        assert len(matches) == 4

        # Remove recurrence
        _update_single_event(connector, fresh_calendar, uid, recurrence_rule="")

        # Verify now has 1 occurrence
        events = connector.get_events(start_date=_future_date(5, 5, 1), end_date=_future_date(5, 5, 31), calendar_ids=[fresh_calendar])
        matches = [e for e in events if e["uid"] == uid]
        assert len(matches) == 1, f"Expected 1 occurrence after removing recurrence, got {len(matches)}"
        assert matches[0]["is_recurring"] is False

    def test_reschedule_single_occurrence(self, connector, fresh_calendar):
        """Reschedule one occurrence of a recurring event — should create standalone event (#82)."""
        uid = _create_single_event(connector,
            calendar_id=fresh_calendar,
            summary="Reschedule Test",
            start_date=_future_date(5, 6, 5, "10:00:00"),
            end_date=_future_date(5, 6, 5, "11:00:00"),
            recurrence_rule="FREQ=WEEKLY;COUNT=3",
            location="Room A",
        )
        # Give EventKit time to fully register the recurring event.
        # Recurring event occurrence lookup is timing-sensitive in Calendar.app.
        time.sleep(2)

        # Verify 3 occurrences
        events = connector.get_events(start_date=_future_date(5, 6, 1), end_date=_future_date(5, 6, 30), calendar_ids=[fresh_calendar])
        series = sorted([e for e in events if e["uid"] == uid], key=lambda e: e["start_date"])
        assert len(series) == 3

        # Use occurrence_date (not start_date) — this matches what the Swift
        # helper's predicate expects (event.occurrenceDate)
        second_occ = series[1]
        second_occ_date_str = second_occ["occurrence_date"]
        second_occ_day = second_occ_date_str[:10]
        # Retry: EventKit may not have fully materialized the occurrence yet
        for attempt in range(3):
            try:
                _update_single_event(connector, fresh_calendar, uid,
                    start_date=f"{second_occ_day}T14:00:00",
                    end_date=f"{second_occ_day}T15:00:00",
                    occurrence_date=second_occ_date_str,
                    span="this_event",
                )
                break
            except (RuntimeError, ValueError) as e:
                if "not found" in str(e).lower() and attempt < 2:
                    time.sleep(1)
                    continue
                raise

        # Check results
        events = connector.get_events(start_date=_future_date(5, 6, 1), end_date=_future_date(5, 6, 30), calendar_ids=[fresh_calendar])

        # Series should still have occurrences
        remaining_series = [e for e in events if e["uid"] == uid]
        assert len(remaining_series) >= 2, (
            f"Series should still have at least 2 occurrences, got {len(remaining_series)}"
        )

        # A rescheduled event should exist at 2pm on the same day
        rescheduled = [e for e in events if second_occ_day in e["start_date"] and "14:00" in e["start_date"]]
        assert len(rescheduled) == 1, f"Should have one event at 2pm on {second_occ_day}, got {len(rescheduled)}"
        assert rescheduled[0]["summary"] == "Reschedule Test"
        # Note: location preservation on recurring event reschedule is unreliable
        # in Calendar.app — EventKit may return nil for occurrence-level location.
        # We verify the reschedule itself worked (summary, time) but don't assert location.

    def test_create_event_with_structured_recurrence(self, connector, fresh_calendar):
        """Create a recurring event using structured recurrence object instead of RRULE string."""
        result = connector.create_events(events=[{
            "summary": "Structured Recurrence Test",
            "start_date": _future_date(5, 7, 7, "10:00:00"),
            "end_date": _future_date(5, 7, 7, "11:00:00"),
            "recurrence": {
                "frequency": "weekly",
                "interval": 1,
                "count": 3,
            },
        }], calendar_id=fresh_calendar)
        uid = result["created"][0]["uid"]
        events = connector.get_events(start_date=_future_date(5, 7, 1), end_date=_future_date(5, 7, 31), calendar_ids=[fresh_calendar])
        recurring = [e for e in events if e["uid"] == uid]
        assert len(recurring) == 3, f"Expected 3 occurrences, got {len(recurring)}"
        # Verify recurrence_parsed is returned
        assert recurring[0].get("recurrence_parsed") is not None
        parsed = recurring[0]["recurrence_parsed"]
        assert parsed["frequency"] == "weekly"
        assert parsed["interval"] == 1
        assert parsed["count"] == 3

    def test_structured_recurrence_with_days_of_week(self, connector, fresh_calendar):
        """Structured recurrence with days_of_week should create occurrences on specified days."""
        # Find next Monday in year+5
        mon = _nth_weekday(5, 8, 0, 1)  # 1st Monday of Aug
        result = connector.create_events(events=[{
            "summary": "MWF Structured Test",
            "start_date": f"{mon.isoformat()}T09:00:00",
            "end_date": f"{mon.isoformat()}T10:00:00",
            "recurrence": {
                "frequency": "weekly",
                "days_of_week": ["MO", "WE", "FR"],
                "count": 6,
            },
        }], calendar_id=fresh_calendar)
        uid = result["created"][0]["uid"]
        events = connector.get_events(start_date=_future_date(5, 8, 1), end_date=_future_date(5, 8, 31), calendar_ids=[fresh_calendar])
        recurring = [e for e in events if e["uid"] == uid]
        assert len(recurring) == 6, f"Expected 6 occurrences (MWF x 2 weeks), got {len(recurring)}"


class TestRoundTripIntegration:
    """Round-trip tests: create → read → use returned data to query again."""

    def test_created_event_fields_match_input(self, connector, test_calendar_id):
        """Create event with all fields, read back, verify every field matches."""
        uid = _create_single_event(connector,
            calendar_id=test_calendar_id,
            summary="Round Trip Test",
            start_date=_future_date(4, 3, 1, "14:00:00"),
            end_date=_future_date(4, 3, 1, "15:00:00"),
            location="Conference Room",
            notes="Testing round-trip",
            url="https://example.com/test",
        )
        try:
            events = connector.get_events(start_date=_future_date(4, 3, 1), end_date=_future_date(4, 3, 2), calendar_ids=[test_calendar_id])
            matches = [e for e in events if e["uid"] == uid]
            assert len(matches) == 1
            event = matches[0]
            assert event["summary"] == "Round Trip Test"
            assert event["location"] == "Conference Room"
            assert event["notes"] == "Testing round-trip"
            assert event["url"] == "https://example.com/test"
            assert event["calendar_name"] == TEST_CALENDAR
        finally:
            _delete_event_by_uid(uid)

    def test_returned_timestamps_usable_for_requery(self, connector, test_calendar_id):
        """Create event, read timestamps, use them to query again — timezone round-trip."""
        uid = _create_single_event(connector,
            calendar_id=test_calendar_id,
            summary="Timestamp Round Trip",
            start_date=_future_date(4, 3, 15, "10:00:00"),
            end_date=_future_date(4, 3, 15, "11:00:00"),
        )
        try:
            # First query: wide range
            events = connector.get_events(start_date=_future_date(4, 3, 15), end_date=_future_date(4, 3, 16), calendar_ids=[test_calendar_id])
            matches = [e for e in events if e["uid"] == uid]
            assert len(matches) == 1

            # Use returned timestamps for a second, narrow query
            returned_start = matches[0]["start_date"]
            returned_end = matches[0]["end_date"]
            events2 = connector.get_events(start_date=returned_start, end_date=returned_end, calendar_ids=[test_calendar_id])
            matches2 = [e for e in events2 if e["uid"] == uid]
            assert len(matches2) == 1, (
                f"Event not found using returned timestamps: start={returned_start}, end={returned_end}"
            )
        finally:
            _delete_event_by_uid(uid)

    def test_returned_timestamps_without_z_suffix(self, connector, test_calendar_id):
        """Simulate Claude stripping Z from timestamps — should still find the event."""
        uid = _create_single_event(connector,
            calendar_id=test_calendar_id,
            summary="Stripped Z Test",
            start_date=_future_date(4, 3, 20, "14:00:00"),
            end_date=_future_date(4, 3, 20, "15:00:00"),
        )
        try:
            events = connector.get_events(start_date=_future_date(4, 3, 20), end_date=_future_date(4, 3, 21), calendar_ids=[test_calendar_id])
            matches = [e for e in events if e["uid"] == uid]
            assert len(matches) == 1

            # Strip any Z suffix (simulating what Claude Desktop does)
            returned_start = matches[0]["start_date"].rstrip("Z")
            returned_end = matches[0]["end_date"].rstrip("Z")

            # Should still find the event
            events2 = connector.get_events(start_date=returned_start, end_date=returned_end, calendar_ids=[test_calendar_id])
            matches2 = [e for e in events2 if e["uid"] == uid]
            assert len(matches2) == 1, (
                f"Event not found with stripped-Z timestamps: start={returned_start}, end={returned_end}"
            )
        finally:
            _delete_event_by_uid(uid)

    def test_update_then_read_back(self, connector, test_calendar_id):
        """Create → update → read back → verify only updated fields changed."""
        uid = _create_single_event(connector,
            calendar_id=test_calendar_id,
            summary="Before Update",
            start_date=_future_date(4, 4, 1, "09:00:00"),
            end_date=_future_date(4, 4, 1, "10:00:00"),
            location="Room A",
        )
        try:
            _update_single_event(connector, test_calendar_id, uid, summary="After Update")
            events = connector.get_events(start_date=_future_date(4, 4, 1), end_date=_future_date(4, 4, 2), calendar_ids=[test_calendar_id])
            matches = [e for e in events if e["uid"] == uid]
            assert len(matches) == 1
            assert matches[0]["summary"] == "After Update"
            assert matches[0]["location"] == "Room A"  # unchanged
        finally:
            _delete_event_by_uid(uid)


class TestWorkflowIntegration:
    """Multi-step workflow tests simulating real Claude Desktop usage."""

    def test_full_event_lifecycle(self, connector, test_calendar_id):
        """Create → update → verify → delete → verify gone."""
        uid = _create_single_event(connector,
            calendar_id=test_calendar_id,
            summary="Lifecycle Test",
            start_date=_future_date(4, 5, 1, "10:00:00"),
            end_date=_future_date(4, 5, 1, "11:00:00"),
        )
        try:
            # Update
            _update_single_event(connector, test_calendar_id, uid, summary="Updated Lifecycle")

            # Verify update
            events = connector.get_events(start_date=_future_date(4, 5, 1), end_date=_future_date(4, 5, 2), calendar_ids=[test_calendar_id])
            assert any(e["uid"] == uid and e["summary"] == "Updated Lifecycle" for e in events)

            # Delete
            result = connector.delete_events(calendar_id=test_calendar_id, event_uids=uid)
            assert uid in result["deleted_uids"]

            # Verify gone
            events = connector.get_events(start_date=_future_date(4, 5, 1), end_date=_future_date(4, 5, 2), calendar_ids=[test_calendar_id])
            assert not any(e["uid"] == uid for e in events)
        finally:
            _delete_event_by_uid(uid)

    def test_availability_blocked_by_new_event(self, connector, test_calendar_id):
        """Check availability → create event → re-check → verify slot blocked."""
        # Check initial availability
        slots_before = connector.get_availability(
            start_date=_future_date(4, 6, 1, "09:00:00"), end_date=_future_date(4, 6, 1, "12:00:00"), calendar_ids=[test_calendar_id]
        )
        assert len(slots_before) == 1  # entirely free

        uid = _create_single_event(connector,
            calendar_id=test_calendar_id,
            summary="Block This Slot",
            start_date=_future_date(4, 6, 1, "10:00:00"),
            end_date=_future_date(4, 6, 1, "11:00:00"),
        )
        try:
            # Re-check availability
            slots_after = connector.get_availability(
                start_date=_future_date(4, 6, 1, "09:00:00"), end_date=_future_date(4, 6, 1, "12:00:00"), calendar_ids=[test_calendar_id]
            )
            assert len(slots_after) == 2  # split into two free slots
            assert slots_after[0]["end_date"] == _future_date(4, 6, 1, "10:00:00")
            assert slots_after[1]["start_date"] == _future_date(4, 6, 1, "11:00:00")
        finally:
            _delete_event_by_uid(uid)


class TestTimezoneIntegration:
    """Timezone edge case tests."""

    def test_event_near_midnight(self, connector, test_calendar_id):
        """Event at 23:30 should be found when querying across midnight."""
        uid = _create_single_event(connector,
            calendar_id=test_calendar_id,
            summary="Late Night Event",
            start_date=_future_date(4, 7, 1, "23:30:00"),
            end_date=_future_date(4, 7, 2, "00:30:00"),
        )
        try:
            events = connector.get_events(start_date=_future_date(4, 7, 1, "23:00:00"), end_date=_future_date(4, 7, 2, "01:00:00"), calendar_ids=[test_calendar_id])
            matches = [e for e in events if e["uid"] == uid]
            assert len(matches) == 1
        finally:
            _delete_event_by_uid(uid)

    def test_allday_event_fields(self, connector, test_calendar_id):
        """All-day event should return allday_event=True with inclusive end_date."""
        uid = _create_single_event(connector,
            calendar_id=test_calendar_id,
            summary="All Day Test",
            start_date=_future_date(4, 8, 1),
            end_date=_future_date(4, 8, 1),
            allday_event=True,
        )
        try:
            events = connector.get_events(start_date=_future_date(4, 8, 1), end_date=_future_date(4, 8, 3), calendar_ids=[test_calendar_id])
            matches = [e for e in events if e["uid"] == uid]
            assert len(matches) == 1
            assert matches[0]["allday_event"] is True
            assert _future_date(4, 8, 1) in matches[0]["end_date"]
        finally:
            _delete_event_by_uid(uid)

    def test_allday_multiday_end_date_inclusive(self, connector, test_calendar_id):
        """Multi-day all-day event end_date should be inclusive: create and read back."""
        start = _future_date(4, 8, 17)
        end = _future_date(4, 8, 23)
        uid = _create_single_event(connector,
            calendar_id=test_calendar_id,
            summary="Week All Day",
            start_date=start,
            end_date=end,
            allday_event=True,
        )
        try:
            events = connector.get_events(start_date=start, end_date=_future_date(4, 8, 25), calendar_ids=[test_calendar_id])
            matches = [e for e in events if e["uid"] == uid]
            assert len(matches) == 1
            assert matches[0]["end_date"] == end
        finally:
            _delete_event_by_uid(uid)

    def test_allday_end_date_round_trip(self, connector, test_calendar_id):
        """All-day end_date should survive create → get → update → get round-trip."""
        start = _future_date(4, 9, 1)
        end = _future_date(4, 9, 5)
        uid = _create_single_event(connector,
            calendar_id=test_calendar_id,
            summary="Round Trip All Day",
            start_date=start,
            end_date=end,
            allday_event=True,
        )
        try:
            # Read back
            events = connector.get_events(start_date=start, end_date=_future_date(4, 9, 7), calendar_ids=[test_calendar_id])
            matches = [e for e in events if e["uid"] == uid]
            assert len(matches) == 1
            assert matches[0]["end_date"] == end

            # Update end_date to extend by one day
            new_end = _future_date(4, 9, 6)
            _update_single_event(connector, test_calendar_id, uid,
                end_date=new_end, allday_event=True)

            # Read back again
            events = connector.get_events(start_date=start, end_date=_future_date(4, 9, 8), calendar_ids=[test_calendar_id])
            matches = [e for e in events if e["uid"] == uid]
            assert len(matches) == 1
            assert matches[0]["end_date"] == new_end
        finally:
            _delete_event_by_uid(uid)

    def test_get_events_inclusive_end_date(self, connector, test_calendar_id):
        """Date-only end_date should be inclusive — events on end_date are returned."""
        date = _future_date(4, 10, 15)
        uid = _create_single_event(connector,
            calendar_id=test_calendar_id,
            summary="Inclusive End Test",
            start_date=date + "T14:00:00",
            end_date=date + "T15:00:00",
        )
        try:
            # Query with date-only end_date matching the event's date
            events = connector.get_events(start_date=date, end_date=date, calendar_ids=[test_calendar_id])
            matches = [e for e in events if e["uid"] == uid]
            assert len(matches) == 1
        finally:
            _delete_event_by_uid(uid)

    def test_explicit_timezone_round_trip(self, connector, test_calendar_id):
        """Event with explicit timezone should round-trip: create → read → requery."""
        uid = _create_single_event(connector,
            calendar_id=test_calendar_id,
            summary="Timezone Round Trip Test",
            start_date=_future_date(5, 5, 15, "09:00:00"),
            end_date=_future_date(5, 5, 15, "10:00:00"),
            timezone="America/New_York",
        )
        try:
            # Read back the event
            events = connector.get_events(start_date=_future_date(5, 5, 15, "00:00:00"), end_date=_future_date(5, 5, 16, "00:00:00"), calendar_ids=[test_calendar_id])
            matches = [e for e in events if e["uid"] == uid]
            assert len(matches) == 1
            returned_start = matches[0]["start_date"]

            # Use the returned timestamp to re-query — this is the round-trip that
            # caught the timezone bug in issue #37
            events2 = connector.get_events(start_date=returned_start, end_date=_future_date(5, 5, 16, "00:00:00"), calendar_ids=[test_calendar_id])
            matches2 = [e for e in events2 if e["uid"] == uid]
            assert len(matches2) == 1, f"Event not found when re-querying with returned start_date '{returned_start}'"
        finally:
            _delete_event_by_uid(uid)


class TestErrorHandlingIntegration:
    """Error handling tests against real Calendar.app."""

    def test_get_events_nonexistent_calendar(self, connector):
        """Querying a non-existent calendar should raise ValueError."""
        with pytest.raises(ValueError, match="not found"):
            connector.get_events(start_date=_future_date(4, 1, 1), end_date=_future_date(4, 1, 2), calendar_ids=["fake-nonexistent-uuid"])

    def test_delete_nonexistent_uid_reports_not_found(self, connector, test_calendar_id):
        """Deleting a non-existent UID should report it, not crash."""
        result = connector.delete_events(calendar_id=test_calendar_id, event_uids="DOES-NOT-EXIST-UID-12345")
        assert result["deleted_uids"] == []
        assert "DOES-NOT-EXIST-UID-12345" in result["not_found_uids"]


class TestSpecialCharactersIntegration:
    """Integration tests for special characters in event fields."""

    def test_create_events_with_special_characters(self, connector, test_calendar_id):
        """Event titles with colons, slashes, apostrophes, and parentheses should round-trip."""
        title = "Lunch w/ John O'Brien: Planning (Q2/Q3)"
        uid = _create_single_event(connector,
            calendar_id=test_calendar_id,
            summary=title,
            start_date=_future_date(4, 11, 1, "12:00:00"),
            end_date=_future_date(4, 11, 1, "13:00:00"),
        )
        try:
            events = connector.get_events(start_date=_future_date(4, 11, 1), end_date=_future_date(4, 11, 2), calendar_ids=[test_calendar_id])
            matches = [e for e in events if e["uid"] == uid]
            assert len(matches) == 1
            assert matches[0]["summary"] == title
        finally:
            _delete_event_by_uid(uid)


class TestAlertsIntegration:
    """Integration tests for event alerts/reminders."""

    def test_create_events_with_multiple_alerts(self, connector, test_calendar_id):
        """Creating an event with multiple alerts should preserve all of them."""
        uid = _create_single_event(connector,
            calendar_id=test_calendar_id,
            summary="Multi Alert Test",
            start_date=_future_date(4, 11, 5, "10:00:00"),
            end_date=_future_date(4, 11, 5, "11:00:00"),
            alert_minutes=[0, 15, 30, 60],
        )
        try:
            events = connector.get_events(start_date=_future_date(4, 11, 5), end_date=_future_date(4, 11, 6), calendar_ids=[test_calendar_id])
            matches = [e for e in events if e["uid"] == uid]
            assert len(matches) == 1
            alerts = matches[0].get("alerts", [])
            alert_values = sorted([a["minutes_before"] for a in alerts])
            assert alert_values == [0, 15, 30, 60], (
                f"Expected alerts [0, 15, 30, 60], got {alert_values}"
            )
        finally:
            _delete_event_by_uid(uid)

    def test_alert_at_zero_minutes(self, connector, test_calendar_id):
        """Alert at 0 minutes (at time of event) should not be dropped as falsy."""
        uid = _create_single_event(connector,
            calendar_id=test_calendar_id,
            summary="Zero Alert Test",
            start_date=_future_date(4, 11, 6, "10:00:00"),
            end_date=_future_date(4, 11, 6, "11:00:00"),
            alert_minutes=[0],
        )
        try:
            events = connector.get_events(start_date=_future_date(4, 11, 6), end_date=_future_date(4, 11, 7), calendar_ids=[test_calendar_id])
            matches = [e for e in events if e["uid"] == uid]
            assert len(matches) == 1
            alerts = matches[0].get("alerts", [])
            assert len(alerts) == 1, f"Expected 1 alert, got {len(alerts)}"
            assert alerts[0]["minutes_before"] == 0
        finally:
            _delete_event_by_uid(uid)

    def test_absolute_date_alarm(self, connector, test_calendar_id):
        """Create event with absolute date alarm — alarm fires at a specific time."""
        result = connector.create_events(events=[{
            "summary": "Absolute Alarm Test",
            "start_date": _future_date(4, 11, 10, "14:00:00"),
            "end_date": _future_date(4, 11, 10, "15:00:00"),
            "alerts": [{"type": "absolute", "date": _future_date(4, 11, 10, "13:00:00")}],
        }], calendar_id=test_calendar_id)
        uid = result["created"][0]["uid"]
        try:
            events = connector.get_events(start_date=_future_date(4, 11, 10), end_date=_future_date(4, 11, 11), calendar_ids=[test_calendar_id])
            matches = [e for e in events if e["uid"] == uid]
            assert len(matches) == 1
            alerts = matches[0].get("alerts", [])
            assert len(alerts) == 1
            assert alerts[0]["type"] == "absolute"
            assert "13:00:00" in alerts[0]["date"]
        finally:
            _delete_event_by_uid(uid)


class TestSearchEventsIntegration:
    """Integration tests for search_events."""

    def test_search_events_multi_month(self, connector, test_calendar_id):
        """Keyword search across a multi-month range should find a matching event."""
        keyword = f"UniqueSearch{uuid.uuid4().hex[:8]}"
        uid = _create_single_event(connector,
            calendar_id=test_calendar_id,
            summary=f"Meeting about {keyword}",
            start_date=_future_date(4, 12, 15, "10:00:00"),
            end_date=_future_date(4, 12, 15, "11:00:00"),
        )
        try:
            results = connector.search_events(
                query=keyword,
                calendar_ids=[test_calendar_id],
                start_date=_future_date(4, 10, 1),
                end_date=_future_date(5, 4, 1),
            )
            assert len(results) >= 1, f"Expected to find event with keyword '{keyword}'"
            assert any(keyword in e["summary"] for e in results)
        finally:
            _delete_event_by_uid(uid)

    def test_search_finds_event_by_notes(self, connector, test_calendar_id):
        """Search should match keywords in event notes."""
        keyword = f"NotesKey{uuid.uuid4().hex[:8]}"
        uid = _create_single_event(connector,
            calendar_id=test_calendar_id,
            summary="Generic Meeting",
            start_date=_future_date(5, 1, 20, "10:00:00"),
            end_date=_future_date(5, 1, 20, "11:00:00"),
            notes=f"Remember to discuss {keyword} topic",
        )
        try:
            results = connector.search_events(
                query=keyword,
                calendar_ids=[test_calendar_id],
                start_date=_future_date(5, 1, 1),
                end_date=_future_date(5, 2, 1),
            )
            assert len(results) >= 1, f"Expected to find event with notes keyword '{keyword}'"
        finally:
            _delete_event_by_uid(uid)

    def test_search_finds_event_by_location(self, connector, test_calendar_id):
        """Search should match keywords in event location."""
        keyword = f"LocKey{uuid.uuid4().hex[:8]}"
        uid = _create_single_event(connector,
            calendar_id=test_calendar_id,
            summary="Office Meeting",
            start_date=_future_date(5, 2, 20, "10:00:00"),
            end_date=_future_date(5, 2, 20, "11:00:00"),
            location=f"Building {keyword}",
        )
        try:
            results = connector.search_events(
                query=keyword,
                calendar_ids=[test_calendar_id],
                start_date=_future_date(5, 2, 1),
                end_date=_future_date(5, 3, 1),
            )
            assert len(results) >= 1, f"Expected to find event with location keyword '{keyword}'"
        finally:
            _delete_event_by_uid(uid)

    def test_search_returns_empty_for_no_match(self, connector, test_calendar_id):
        """Search for a nonexistent keyword should return empty results."""
        nonsense = f"ZZZZZ{uuid.uuid4().hex}"
        results = connector.search_events(
            query=nonsense,
            calendar_ids=[test_calendar_id],
            start_date=_future_date(5, 1, 1),
            end_date=_future_date(5, 12, 31),
        )
        assert results == []

    def test_search_across_all_calendars(self, connector, test_calendar_id):
        """Search without specifying calendar_names should search all calendars."""
        keyword = f"AllCalSearch{uuid.uuid4().hex[:8]}"
        uid = _create_single_event(connector,
            calendar_id=test_calendar_id,
            summary=f"Findme {keyword}",
            start_date=_future_date(5, 3, 20, "10:00:00"),
            end_date=_future_date(5, 3, 20, "11:00:00"),
        )
        try:
            results = connector.search_events(
                query=keyword,
                start_date=_future_date(5, 3, 1),
                end_date=_future_date(5, 4, 1),
            )
            assert len(results) >= 1, f"Expected to find event across all calendars"
        finally:
            _delete_event_by_uid(uid)


# ── get_conflicts ──────────────────────────────────────────────────────────


class TestGetConflictsIntegration:
    """Integration tests for get_conflicts."""

    def test_overlapping_events_detected(self, connector, test_calendar_id):
        """Two overlapping events should produce a conflict."""
        tag = uuid.uuid4().hex[:8]
        uid1 = _create_single_event(
            connector, test_calendar_id, f"Conflict-A-{tag}",
            _future_date(5, 9, 15, "10:00:00"), _future_date(5, 9, 15, "11:00:00"),
        )
        uid2 = _create_single_event(
            connector, test_calendar_id, f"Conflict-B-{tag}",
            _future_date(5, 9, 15, "10:30:00"), _future_date(5, 9, 15, "11:30:00"),
        )
        try:
            conflicts = connector.get_conflicts(
                start_date=_future_date(5, 9, 15, "00:00:00"), end_date=_future_date(5, 9, 16, "00:00:00"), calendar_ids=[test_calendar_id]
            )
            # Find the conflict involving our events
            our_conflict = [
                c for c in conflicts
                if {c["event_a"]["summary"], c["event_b"]["summary"]}
                == {f"Conflict-A-{tag}", f"Conflict-B-{tag}"}
            ]
            assert len(our_conflict) == 1
            assert our_conflict[0]["overlap_minutes"] == 30
        finally:
            _delete_event_by_uid(uid1)
            _delete_event_by_uid(uid2)

    def test_adjacent_events_no_conflict(self, connector, test_calendar_id):
        """Two adjacent (non-overlapping) events should produce no conflict."""
        tag = uuid.uuid4().hex[:8]
        uid1 = _create_single_event(
            connector, test_calendar_id, f"Adjacent-A-{tag}",
            _future_date(5, 9, 16, "10:00:00"), _future_date(5, 9, 16, "11:00:00"),
        )
        uid2 = _create_single_event(
            connector, test_calendar_id, f"Adjacent-B-{tag}",
            _future_date(5, 9, 16, "11:00:00"), _future_date(5, 9, 16, "12:00:00"),
        )
        try:
            conflicts = connector.get_conflicts(
                start_date=_future_date(5, 9, 16, "00:00:00"), end_date=_future_date(5, 9, 17, "00:00:00"), calendar_ids=[test_calendar_id]
            )
            our_conflicts = [
                c for c in conflicts
                if f"Adjacent-A-{tag}" in (c["event_a"]["summary"], c["event_b"]["summary"])
                or f"Adjacent-B-{tag}" in (c["event_a"]["summary"], c["event_b"]["summary"])
            ]
            assert len(our_conflicts) == 0
        finally:
            _delete_event_by_uid(uid1)
            _delete_event_by_uid(uid2)

    def test_free_event_excluded_from_conflicts(self, connector, test_calendar_id):
        """An event marked availability='free' should not produce conflicts."""
        tag = uuid.uuid4().hex[:8]
        uid1 = _create_single_event(
            connector, test_calendar_id, f"Busy-{tag}",
            _future_date(5, 9, 17, "10:00:00"), _future_date(5, 9, 17, "11:00:00"),
        )
        uid2 = _create_single_event(
            connector, test_calendar_id, f"Free-{tag}",
            _future_date(5, 9, 17, "10:30:00"), _future_date(5, 9, 17, "11:30:00"),
            availability="free",
        )
        try:
            conflicts = connector.get_conflicts(
                start_date=_future_date(5, 9, 17, "00:00:00"), end_date=_future_date(5, 9, 18, "00:00:00"), calendar_ids=[test_calendar_id]
            )
            our_conflicts = [
                c for c in conflicts
                if f"Busy-{tag}" in (c["event_a"]["summary"], c["event_b"]["summary"])
                or f"Free-{tag}" in (c["event_a"]["summary"], c["event_b"]["summary"])
            ]
            assert len(our_conflicts) == 0
        finally:
            _delete_event_by_uid(uid1)
            _delete_event_by_uid(uid2)


# ── batch size limits ──────────────────────────────────────────────────────


class TestBatchLimitsIntegration:
    """Integration tests for per-call batch size limits."""

    def test_create_events_exceeds_batch_limit(self, connector, test_calendar_id):
        events = [{"summary": f"Event {i}", "start_date": _future_date(3, 6, 15, "10:00:00"),
                    "end_date": _future_date(3, 6, 15, "11:00:00")} for i in range(51)]
        with pytest.raises(ValueError, match="exceeds limit of 50"):
            connector.create_events(events=events, calendar_id=test_calendar_id)

    def test_update_events_exceeds_batch_limit(self, connector, test_calendar_id):
        updates = [{"uid": f"UID-{i}", "summary": f"Event {i}"} for i in range(51)]
        with pytest.raises(ValueError, match="exceeds limit of 50"):
            connector.update_events(calendar_id=test_calendar_id, updates=updates)

    def test_delete_events_exceeds_batch_limit(self, connector, test_calendar_id):
        uids = [f"UID-{i}" for i in range(51)]
        with pytest.raises(ValueError, match="exceeds limit of 50"):
            connector.delete_events(calendar_id=test_calendar_id, event_uids=uids)


# ── calendar safety guards ─────────────────────────────────────────────────


class TestCalendarSafetyIntegration:
    """Verify safety guards block destructive operations on non-test calendars."""

    def test_create_events_blocked_on_non_test_calendar(self, connector):
        with pytest.raises(CalendarSafetyError):
            connector.create_events(events=[{"summary": "Test"}], calendar_id="fake-uuid")

    def test_delete_events_blocked_on_non_test_calendar(self, connector):
        with pytest.raises(CalendarSafetyError):
            connector.delete_events(calendar_id="fake-uuid", event_uids="UID-1")

    def test_update_events_blocked_on_non_test_calendar(self, connector):
        with pytest.raises(CalendarSafetyError):
            connector.update_events(calendar_id="fake-uuid", updates=[{"uid": "UID-1", "summary": "Test"}])

    def test_delete_calendar_blocked_on_non_test_calendar(self, connector):
        with pytest.raises(CalendarSafetyError):
            connector.delete_calendar(calendar_id="fake-uuid")
