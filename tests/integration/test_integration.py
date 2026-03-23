"""Integration tests for Apple Calendar MCP — runs against real Calendar.app.

Requires:
    - CALENDAR_TEST_MODE=true environment variable
    - The test calendar is created/deleted automatically by conftest.py

Run with: make test-integration
"""
import os
import re
import uuid

import pytest

from apple_calendar_mcp.calendar_connector import CalendarConnector, run_applescript, run_swift_helper


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


def _update_single_event(connector, calendar_name, event_uid, **kwargs):
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
            # Handle special cases
            if py_key == "location" and value == "":
                update["clear_location"] = True
                continue
            if py_key == "recurrence_rule" and value == "":
                update["clear_recurrence"] = True
                continue
            if py_key == "allday_event":
                update[json_key] = value  # already bool
                continue
            update[json_key] = value
    if "alert_minutes" in kwargs:
        if kwargs["alert_minutes"] == []:
            update["clear_alerts"] = True
        else:
            update["alerts"] = kwargs["alert_minutes"]
    result = connector.update_events(calendar_name, [update])
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


def _create_single_event(connector, calendar_name, summary, start_date, end_date, **kwargs):
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
    result = connector.create_events(calendar_name, [event])
    return result["created"][0]["uid"]


class TestCalendarManagementIntegration:
    """Integration tests for create_calendar and delete_calendar."""

    def test_create_and_delete_calendar(self, connector):
        """Create a calendar, verify it exists, delete it, verify it's gone."""
        cal_name = "MCP-Test-Calendar-2"
        try:
            result = connector.create_calendar(cal_name)
            assert result["name"] == cal_name

            calendars = connector.get_calendars()
            names = [c["name"] for c in calendars]
            assert cal_name in names
        finally:
            try:
                connector.delete_calendar(cal_name)
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
        """Each calendar should have name, writable, description, color, source."""
        calendars = connector.get_calendars()
        for cal in calendars:
            assert "name" in cal, f"Missing 'name' in calendar: {cal}"
            assert "writable" in cal, f"Missing 'writable' in calendar: {cal}"
            assert "description" in cal, f"Missing 'description' in calendar: {cal}"
            assert "color" in cal, f"Missing 'color' in calendar: {cal}"
            assert "source" in cal, f"Missing 'source' in calendar: {cal}"

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

    def test_creates_event_and_returns_uid(self, connector):
        """Creating an event should return a valid UID string."""
        uid = _create_single_event(connector,
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
        uid = _create_single_event(connector,
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
        """Creating an event with location, notes, and URL should succeed."""
        uid = _create_single_event(connector,
            calendar_name=TEST_CALENDAR,
            summary="Full Event Test",
            start_date="2026-06-15T09:00:00",
            end_date="2026-06-15T10:00:00",
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

    def test_creates_allday_event(self, connector):
        """Creating an all-day event should set the allday flag."""
        uid = _create_single_event(connector,
            calendar_name=TEST_CALENDAR,
            summary="All Day Test",
            start_date="2026-06-15",
            end_date="2026-06-15",
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

    def test_batch_creates_multiple_events(self, connector):
        """Batch create should handle multiple events in one call."""
        events = [
            {"summary": "Batch Event 1", "start_date": "2026-06-20T10:00:00", "end_date": "2026-06-20T11:00:00"},
            {"summary": "Batch Event 2", "start_date": "2026-06-20T14:00:00", "end_date": "2026-06-20T15:00:00"},
        ]
        result = connector.create_events(TEST_CALENDAR, events)
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

    def test_get_events_returns_created_event(self, connector):
        """Create an event, then verify get_events returns it."""
        uid = _create_single_event(connector,
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
        uid = _create_single_event(connector,
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
        uid = _create_single_event(connector,
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
                         "location", "notes", "url", "status", "calendar_name"]:
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

    def test_get_events_year_boundary(self, connector):
        """Query spanning Dec 29 – Jan 3 should return events on both sides of year boundary."""
        uid_dec = _create_single_event(connector,
            calendar_name=TEST_CALENDAR,
            summary="Year Boundary Dec 31",
            start_date="2029-12-31T10:00:00",
            end_date="2029-12-31T11:00:00",
        )
        uid_jan = _create_single_event(connector,
            calendar_name=TEST_CALENDAR,
            summary="Year Boundary Jan 2",
            start_date="2030-01-02T10:00:00",
            end_date="2030-01-02T11:00:00",
        )
        try:
            events = connector.get_events(
                calendar_name=TEST_CALENDAR,
                start_date="2029-12-29",
                end_date="2030-01-04",
            )
            uids = [e["uid"] for e in events]
            assert uid_dec in uids, "Dec 31 event not found in year-boundary query"
            assert uid_jan in uids, "Jan 2 event not found in year-boundary query"
        finally:
            _delete_event_by_uid(uid_dec)
            _delete_event_by_uid(uid_jan)


class TestUpdateEventIntegration:
    """Integration tests for update_events against real Calendar.app."""

    def test_update_summary(self, connector):
        """Update summary and verify via get_events."""
        uid = _create_single_event(connector,
            calendar_name=TEST_CALENDAR,
            summary="Original Summary",
            start_date="2026-09-01T10:00:00",
            end_date="2026-09-01T11:00:00",
        )
        try:
            _update_single_event(connector, TEST_CALENDAR, uid, summary="Updated Summary")
            events = connector.get_events(TEST_CALENDAR, "2026-09-01T00:00:00", "2026-09-02T00:00:00")
            test_events = [e for e in events if e["uid"] == uid]
            assert len(test_events) == 1
            assert test_events[0]["summary"] == "Updated Summary"
        finally:
            _delete_event_by_uid(uid)

    def test_update_location(self, connector):
        """Update location from A to B and verify."""
        uid = _create_single_event(connector,
            calendar_name=TEST_CALENDAR,
            summary="Location Update Test",
            start_date="2026-09-02T10:00:00",
            end_date="2026-09-02T11:00:00",
            location="Room A",
        )
        try:
            _update_single_event(connector, TEST_CALENDAR, uid, location="Room B")
            events = connector.get_events(TEST_CALENDAR, "2026-09-02T00:00:00", "2026-09-03T00:00:00")
            test_events = [e for e in events if e["uid"] == uid]
            assert len(test_events) == 1
            assert test_events[0]["location"] == "Room B"
        finally:
            _delete_event_by_uid(uid)

    def test_update_dates(self, connector):
        """Update start/end dates and verify."""
        uid = _create_single_event(connector,
            calendar_name=TEST_CALENDAR,
            summary="Date Update Test",
            start_date="2026-09-03T10:00:00",
            end_date="2026-09-03T11:00:00",
        )
        try:
            _update_single_event(connector, TEST_CALENDAR, uid,
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
        uid = _create_single_event(connector,
            calendar_name=TEST_CALENDAR,
            summary="Multi Update Test",
            start_date="2026-09-04T10:00:00",
            end_date="2026-09-04T11:00:00",
            location="Old Place",
        )
        try:
            result = _update_single_event(connector, TEST_CALENDAR, uid,
                summary="New Multi Title",
                location="New Place",
            )
            assert "summary" in result.get("updated_fields", [])
            assert "location" in result.get("updated_fields", [])
            events = connector.get_events(TEST_CALENDAR, "2026-09-04T00:00:00", "2026-09-05T00:00:00")
            test_events = [e for e in events if e["uid"] == uid]
            assert test_events[0]["summary"] == "New Multi Title"
            assert test_events[0]["location"] == "New Place"
        finally:
            _delete_event_by_uid(uid)

    def test_update_nonexistent_event(self, connector):
        """Updating a non-existent UID should raise an error."""
        with pytest.raises(ValueError, match="Event not found"):
            _update_single_event(connector, TEST_CALENDAR, "DOES-NOT-EXIST-UID", summary="X")

    def test_clear_location(self, connector):
        """Passing location="" should clear the location field."""
        uid = _create_single_event(connector,
            calendar_name=TEST_CALENDAR,
            summary="Clear Location Test",
            start_date="2026-09-05T10:00:00",
            end_date="2026-09-05T11:00:00",
            location="Will Be Cleared",
        )
        try:
            _update_single_event(connector, TEST_CALENDAR, uid, location="")
            events = connector.get_events(TEST_CALENDAR, "2026-09-05T00:00:00", "2026-09-06T00:00:00")
            test_events = [e for e in events if e["uid"] == uid]
            assert len(test_events) == 1
            assert test_events[0]["location"] == ""
        finally:
            _delete_event_by_uid(uid)

    def test_update_title_only(self, connector):
        """Updating only summary should leave location and notes unchanged."""
        uid = _create_single_event(connector,
            calendar_name=TEST_CALENDAR,
            summary="Original Title",
            start_date="2027-09-10T10:00:00",
            end_date="2027-09-10T11:00:00",
            location="Keep This Location",
            notes="Keep these notes",
        )
        try:
            _update_single_event(connector, TEST_CALENDAR, uid, summary="New Title")
            events = connector.get_events(TEST_CALENDAR, "2027-09-10", "2027-09-11")
            matches = [e for e in events if e["uid"] == uid]
            assert len(matches) == 1
            assert matches[0]["summary"] == "New Title"
            assert matches[0]["location"] == "Keep This Location"
            assert matches[0]["notes"] == "Keep these notes"
        finally:
            _delete_event_by_uid(uid)

    def test_update_allday_event_notes_preserves_fields(self, connector):
        """Updating notes on an all-day event should preserve location and all-day status."""
        uid = _create_single_event(connector,
            calendar_name=TEST_CALENDAR,
            summary="All Day Update Test",
            start_date="2027-09-15",
            end_date="2027-09-15",
            allday_event=True,
            location="Conference Room",
            notes="Original notes",
        )
        try:
            _update_single_event(connector, TEST_CALENDAR, uid, notes="Updated notes")
            events = connector.get_events(TEST_CALENDAR, "2027-09-15", "2027-09-17")
            matches = [e for e in events if e["uid"] == uid]
            assert len(matches) == 1
            assert matches[0]["notes"] == "Updated notes"
            assert matches[0]["location"] == "Conference Room"
            assert matches[0]["allday_event"] is True
        finally:
            _delete_event_by_uid(uid)

    def test_reschedule_event_to_different_day(self, connector):
        """Moving an event to a different day should update dates and preserve other fields."""
        uid = _create_single_event(connector,
            calendar_name=TEST_CALENDAR,
            summary="Reschedule Day Test",
            start_date="2027-09-20T10:00:00",
            end_date="2027-09-20T11:00:00",
            location="Room B",
            notes="Important meeting",
        )
        try:
            _update_single_event(connector, TEST_CALENDAR, uid,
                start_date="2027-09-25T14:00:00",
                end_date="2027-09-25T15:00:00",
            )
            # Query the new date range
            events = connector.get_events(TEST_CALENDAR, "2027-09-25", "2027-09-26")
            matches = [e for e in events if e["uid"] == uid]
            assert len(matches) == 1
            assert "2027-09-25" in matches[0]["start_date"]
            assert "14:00" in matches[0]["start_date"]
            assert matches[0]["location"] == "Room B"
            assert matches[0]["notes"] == "Important meeting"

            # Verify not at original date
            old_events = connector.get_events(TEST_CALENDAR, "2027-09-20", "2027-09-21")
            assert not any(e["uid"] == uid for e in old_events)
        finally:
            _delete_event_by_uid(uid)


class TestDeleteEventsIntegration:
    """Integration tests for delete_events against real Calendar.app."""

    def test_delete_single_event(self, connector):
        """Create event, delete it, verify it's gone via get_events."""
        uid = _create_single_event(connector,
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
            uid = _create_single_event(connector,
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
        uid = _create_single_event(connector,
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

    def test_delete_single_occurrence_of_recurring(self, connector, fresh_calendar):
        """Delete one occurrence of a recurring event, verify others preserved (#84)."""
        uid = _create_single_event(connector,
            calendar_name=TEST_CALENDAR,
            summary="Delete Occurrence Test",
            start_date="2028-08-07T10:00:00",
            end_date="2028-08-07T11:00:00",
            recurrence_rule="FREQ=WEEKLY;COUNT=3",
        )
        # Verify 3 occurrences: Aug 7, 14, 21
        events = connector.get_events(TEST_CALENDAR, "2028-08-01", "2028-08-31")
        series = [e for e in events if e["uid"] == uid]
        assert len(series) == 3

        # Delete the middle occurrence (Aug 14)
        result = connector.delete_events(
            TEST_CALENDAR, uid,
            span="this_event",
            occurrence_date="2028-08-14T10:00:00",
        )
        assert uid in result["deleted_uids"]

        # Verify 2 remaining occurrences (Aug 7 and 21)
        events = connector.get_events(TEST_CALENDAR, "2028-08-01", "2028-08-31")
        remaining = [e for e in events if e["uid"] == uid]
        assert len(remaining) == 2, f"Expected 2 occurrences after deleting one, got {len(remaining)}"
        dates = sorted([e["start_date"][:10] for e in remaining])
        assert "2028-08-14" not in dates, "Deleted occurrence should be gone"

    def test_delete_non_recurring_event_then_verify_absent(self, connector):
        """Delete a non-recurring event and verify it's absent via re-query (round-trip)."""
        uid = _create_single_event(connector,
            calendar_name=TEST_CALENDAR,
            summary="Delete Verify Test",
            start_date="2027-10-10T10:00:00",
            end_date="2027-10-10T11:00:00",
        )
        # Verify it exists
        events = connector.get_events(TEST_CALENDAR, "2027-10-10", "2027-10-11")
        assert any(e["uid"] == uid for e in events), "Event should exist before deletion"

        # Delete it
        result = connector.delete_events(TEST_CALENDAR, uid)
        assert uid in result["deleted_uids"]

        # Verify absent via re-query
        events = connector.get_events(TEST_CALENDAR, "2027-10-10", "2027-10-11")
        assert not any(e["uid"] == uid for e in events), "Event should be absent after deletion"

    def test_delete_recurring_series_with_future_events(self, connector, fresh_calendar):
        """Delete a recurring series using span=future_events (#84)."""
        uid = _create_single_event(connector,
            calendar_name=TEST_CALENDAR,
            summary="Delete Series Test",
            start_date="2028-09-02T10:00:00",
            end_date="2028-09-02T11:00:00",
            recurrence_rule="FREQ=WEEKLY;COUNT=4",
        )
        events = connector.get_events(TEST_CALENDAR, "2028-09-01", "2028-09-30")
        series = [e for e in events if e["uid"] == uid]
        assert len(series) == 4

        # Delete entire series
        result = connector.delete_events(TEST_CALENDAR, uid, span="future_events")
        assert uid in result["deleted_uids"]

        # Verify all gone
        events = connector.get_events(TEST_CALENDAR, "2028-09-01", "2028-09-30")
        remaining = [e for e in events if e["uid"] == uid]
        assert len(remaining) == 0, f"Expected 0 occurrences after deleting series, got {len(remaining)}"


class TestGetAvailabilityIntegration:
    """Integration tests for get_availability against real Calendar.app."""

    def test_free_slots_around_event(self, connector):
        """Create an event and verify free slots before and after it."""
        uid = _create_single_event(connector,
            calendar_name=TEST_CALENDAR,
            summary="Availability Test",
            start_date="2026-11-01T10:00:00",
            end_date="2026-11-01T11:00:00",
        )
        try:
            slots = connector.get_availability(
                calendar_names=[TEST_CALENDAR],
                start_date="2026-11-01T09:00:00",
                end_date="2026-11-01T12:00:00",
            )
            assert len(slots) == 2
            assert slots[0]["end_date"] == "2026-11-01T10:00:00"
            assert slots[1]["start_date"] == "2026-11-01T11:00:00"
        finally:
            _delete_event_by_uid(uid)

    def test_no_events_entire_range_free(self, connector):
        """Empty date range should return single free slot."""
        slots = connector.get_availability(
            calendar_names=[TEST_CALENDAR],
            start_date="2099-06-01T09:00:00",
            end_date="2099-06-01T17:00:00",
        )
        assert len(slots) == 1
        assert slots[0]["duration_minutes"] == 480

    def test_min_duration_filters_short_slots(self, connector):
        """Create event leaving short gaps, verify min_duration filters them."""
        uid = _create_single_event(connector,
            calendar_name=TEST_CALENDAR,
            summary="Availability Filter Test",
            start_date="2099-07-01T09:20:00",
            end_date="2099-07-01T10:00:00",
        )
        try:
            # Without filter: 9:00-9:20 (20m) and 10:00-12:00 (120m)
            all_slots = connector.get_availability(
                calendar_names=[TEST_CALENDAR],
                start_date="2099-07-01T09:00:00",
                end_date="2099-07-01T12:00:00",
            )
            assert len(all_slots) == 2

            # With filter: only 10:00-12:00 (120m) passes
            filtered = connector.get_availability(
                calendar_names=[TEST_CALENDAR],
                start_date="2099-07-01T09:00:00",
                end_date="2099-07-01T12:00:00",
                min_duration_minutes=30,
            )
            assert len(filtered) == 1
            assert filtered[0]["start_date"] == "2099-07-01T10:00:00"
            assert filtered[0]["duration_minutes"] == 120
        finally:
            _delete_event_by_uid(uid)

    def test_working_hours_clips_range(self, connector):
        """Working hours clip free slots to the specified window."""
        slots = connector.get_availability(
            calendar_names=[TEST_CALENDAR],
            start_date="2099-08-01T00:00:00",
            end_date="2099-08-02T00:00:00",
            working_hours_start="09:00",
            working_hours_end="17:00",
        )
        assert len(slots) == 1
        assert slots[0]["start_date"] == "2099-08-01T09:00:00"
        assert slots[0]["end_date"] == "2099-08-01T17:00:00"
        assert slots[0]["duration_minutes"] == 480


class TestRecurringEventsIntegration:
    """Integration tests for recurring event handling."""

    def test_create_recurring_event_and_read_occurrences(self, connector, fresh_calendar):
        """Create a recurring event, verify multiple occurrences returned with recurrence fields."""
        uid = _create_single_event(connector,
            calendar_name=TEST_CALENDAR,
            summary="Recurring Test",
            start_date="2027-01-05T10:00:00",
            end_date="2027-01-05T11:00:00",
            recurrence_rule="FREQ=WEEKLY;COUNT=3",
        )
        events = connector.get_events(
            calendar_name=TEST_CALENDAR,
            start_date="2027-01-01",
            end_date="2027-01-31",
        )
        recurring = [e for e in events if e["uid"] == uid]
        assert len(recurring) == 3

        # All share the same UID
        assert all(e["uid"] == uid for e in recurring)

        # All have recurrence fields
        for evt in recurring:
            assert evt["is_recurring"] is True
            assert "FREQ=WEEKLY" in evt["recurrence_rule"]
            assert evt["is_detached"] is False

        # Each has a different occurrence_date
        occ_dates = [e["occurrence_date"] for e in recurring]
        assert len(set(occ_dates)) == 3

    def test_monthly_nth_weekday_recurrence(self, connector, fresh_calendar):
        """Create monthly event on 4th Monday — verify correct dates (#79)."""
        # Jan 26 2028 is a 4th Monday
        uid = _create_single_event(connector,
            calendar_name=TEST_CALENDAR,
            summary="4th Monday Test",
            start_date="2028-01-26T10:00:00",
            end_date="2028-01-26T11:00:00",
            recurrence_rule="FREQ=MONTHLY;BYDAY=4MO;COUNT=3",
        )
        events = connector.get_events(
            calendar_name=TEST_CALENDAR,
            start_date="2028-01-01",
            end_date="2028-04-30",
        )
        recurring = [e for e in events if e["uid"] == uid]
        assert len(recurring) == 3, f"Expected 3 occurrences, got {len(recurring)}"

        # Verify dates are all 4th Mondays
        dates = sorted([e["start_date"][:10] for e in recurring])
        assert dates[0] == "2028-01-26"  # 4th Monday of Jan
        assert dates[1] == "2028-02-28"  # 4th Monday of Feb
        assert dates[2] == "2028-03-27"  # 4th Monday of Mar

    def test_recurrence_with_until_end_date(self, connector, fresh_calendar):
        """Create weekly event with UNTIL — verify recurrence stops (#81)."""
        uid = _create_single_event(connector,
            calendar_name=TEST_CALENDAR,
            summary="Until Test",
            start_date="2028-03-01T10:00:00",
            end_date="2028-03-01T11:00:00",
            recurrence_rule="FREQ=WEEKLY;UNTIL=20280322T000000",
        )
        events = connector.get_events(
            calendar_name=TEST_CALENDAR,
            start_date="2028-03-01",
            end_date="2028-04-30",
        )
        recurring = [e for e in events if e["uid"] == uid]
        # Should have ~3 occurrences (Mar 1, 8, 15) — Mar 22 is the UNTIL date
        assert len(recurring) <= 4, f"Should stop by March 22, got {len(recurring)} occurrences"
        assert len(recurring) >= 3, f"Should have at least 3 occurrences, got {len(recurring)}"

        # No occurrence should be on or after March 22
        for e in recurring:
            assert e["start_date"][:10] < "2028-03-22", (
                f"Occurrence {e['start_date']} should be before UNTIL date 2028-03-22"
            )

    def test_last_friday_recurrence(self, connector, fresh_calendar):
        """Create monthly event on last Friday (BYDAY=-1FR) — verify correct dates (#79)."""
        # Jan 27 2028 is the last Friday of January
        uid = _create_single_event(connector,
            calendar_name=TEST_CALENDAR,
            summary="Last Friday Test",
            start_date="2028-01-28T10:00:00",
            end_date="2028-01-28T11:00:00",
            recurrence_rule="FREQ=MONTHLY;BYDAY=-1FR;COUNT=3",
        )
        events = connector.get_events(
            calendar_name=TEST_CALENDAR,
            start_date="2028-01-01",
            end_date="2028-04-30",
        )
        recurring = [e for e in events if e["uid"] == uid]
        assert len(recurring) == 3, f"Expected 3 occurrences, got {len(recurring)}"

        dates = sorted([e["start_date"][:10] for e in recurring])
        assert dates[0] == "2028-01-28"  # Last Friday of Jan
        assert dates[1] == "2028-02-25"  # Last Friday of Feb
        assert dates[2] == "2028-03-31"  # Last Friday of Mar

    def test_add_recurrence_to_existing_event(self, connector, fresh_calendar):
        """Create non-recurring event, add recurrence via update (#80)."""
        uid = _create_single_event(connector,
            calendar_name=TEST_CALENDAR,
            summary="Add Recurrence Test",
            start_date="2028-04-03T10:00:00",
            end_date="2028-04-03T11:00:00",
        )
        # Verify starts as non-recurring
        events = connector.get_events(TEST_CALENDAR, "2028-04-01", "2028-04-30")
        matches = [e for e in events if e["uid"] == uid]
        assert len(matches) == 1
        assert matches[0]["is_recurring"] is False

        # Add weekly recurrence
        _update_single_event(connector, TEST_CALENDAR, uid, recurrence_rule="FREQ=WEEKLY;COUNT=3")

        # Verify now has 3 occurrences
        events = connector.get_events(TEST_CALENDAR, "2028-04-01", "2028-04-30")
        matches = [e for e in events if e["uid"] == uid]
        assert len(matches) == 3, f"Expected 3 occurrences, got {len(matches)}"
        assert all(e["is_recurring"] for e in matches)

    def test_remove_recurrence_from_event(self, connector, fresh_calendar):
        """Create recurring event, remove recurrence via update (#80)."""
        uid = _create_single_event(connector,
            calendar_name=TEST_CALENDAR,
            summary="Remove Recurrence Test",
            start_date="2028-05-01T10:00:00",
            end_date="2028-05-01T11:00:00",
            recurrence_rule="FREQ=WEEKLY;COUNT=4",
        )
        # Verify starts with 4 occurrences
        events = connector.get_events(TEST_CALENDAR, "2028-05-01", "2028-05-31")
        matches = [e for e in events if e["uid"] == uid]
        assert len(matches) == 4

        # Remove recurrence
        _update_single_event(connector, TEST_CALENDAR, uid, recurrence_rule="")

        # Verify now has 1 occurrence
        events = connector.get_events(TEST_CALENDAR, "2028-05-01", "2028-05-31")
        matches = [e for e in events if e["uid"] == uid]
        assert len(matches) == 1, f"Expected 1 occurrence after removing recurrence, got {len(matches)}"
        assert matches[0]["is_recurring"] is False

    def test_reschedule_single_occurrence(self, connector, fresh_calendar):
        """Reschedule one occurrence of a recurring event — should create standalone event (#82)."""
        uid = _create_single_event(connector,
            calendar_name=TEST_CALENDAR,
            summary="Reschedule Test",
            start_date="2028-06-05T10:00:00",
            end_date="2028-06-05T11:00:00",
            recurrence_rule="FREQ=WEEKLY;COUNT=3",
            location="Room A",
        )
        # Verify 3 occurrences: Jun 5, 12, 19
        events = connector.get_events(TEST_CALENDAR, "2028-06-01", "2028-06-30")
        series = [e for e in events if e["uid"] == uid]
        assert len(series) == 3

        # Reschedule the Jun 12 occurrence to 2pm
        _update_single_event(connector, TEST_CALENDAR, uid,
            start_date="2028-06-12T14:00:00",
            end_date="2028-06-12T15:00:00",
            occurrence_date="2028-06-12T10:00:00",
            span="this_event",
        )

        # Check results
        events = connector.get_events(TEST_CALENDAR, "2028-06-01", "2028-06-30")

        # Series should still have occurrences (Jun 5 and Jun 19 at 10am)
        remaining_series = [e for e in events if e["uid"] == uid]
        assert len(remaining_series) >= 2, (
            f"Series should still have at least 2 occurrences, got {len(remaining_series)}"
        )

        # A standalone event should exist at 2pm on Jun 12 with same summary and location
        jun12_events = [e for e in events if "2028-06-12" in e["start_date"]]
        assert len(jun12_events) >= 1, "Should have an event on Jun 12 at the new time"
        rescheduled = [e for e in jun12_events if "14:00" in e["start_date"]]
        assert len(rescheduled) == 1, f"Should have one event at 2pm on Jun 12, got {len(rescheduled)}"
        assert rescheduled[0]["summary"] == "Reschedule Test"
        assert rescheduled[0]["location"] == "Room A"


class TestRoundTripIntegration:
    """Round-trip tests: create → read → use returned data to query again."""

    def test_created_event_fields_match_input(self, connector):
        """Create event with all fields, read back, verify every field matches."""
        uid = _create_single_event(connector,
            calendar_name=TEST_CALENDAR,
            summary="Round Trip Test",
            start_date="2027-03-01T14:00:00",
            end_date="2027-03-01T15:00:00",
            location="Conference Room",
            notes="Testing round-trip",
            url="https://example.com/test",
        )
        try:
            events = connector.get_events(TEST_CALENDAR, "2027-03-01", "2027-03-02")
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

    def test_returned_timestamps_usable_for_requery(self, connector):
        """Create event, read timestamps, use them to query again — timezone round-trip."""
        uid = _create_single_event(connector,
            calendar_name=TEST_CALENDAR,
            summary="Timestamp Round Trip",
            start_date="2027-03-15T10:00:00",
            end_date="2027-03-15T11:00:00",
        )
        try:
            # First query: wide range
            events = connector.get_events(TEST_CALENDAR, "2027-03-15", "2027-03-16")
            matches = [e for e in events if e["uid"] == uid]
            assert len(matches) == 1

            # Use returned timestamps for a second, narrow query
            returned_start = matches[0]["start_date"]
            returned_end = matches[0]["end_date"]
            events2 = connector.get_events(TEST_CALENDAR, returned_start, returned_end)
            matches2 = [e for e in events2 if e["uid"] == uid]
            assert len(matches2) == 1, (
                f"Event not found using returned timestamps: start={returned_start}, end={returned_end}"
            )
        finally:
            _delete_event_by_uid(uid)

    def test_returned_timestamps_without_z_suffix(self, connector):
        """Simulate Claude stripping Z from timestamps — should still find the event."""
        uid = _create_single_event(connector,
            calendar_name=TEST_CALENDAR,
            summary="Stripped Z Test",
            start_date="2027-03-20T14:00:00",
            end_date="2027-03-20T15:00:00",
        )
        try:
            events = connector.get_events(TEST_CALENDAR, "2027-03-20", "2027-03-21")
            matches = [e for e in events if e["uid"] == uid]
            assert len(matches) == 1

            # Strip any Z suffix (simulating what Claude Desktop does)
            returned_start = matches[0]["start_date"].rstrip("Z")
            returned_end = matches[0]["end_date"].rstrip("Z")

            # Should still find the event
            events2 = connector.get_events(TEST_CALENDAR, returned_start, returned_end)
            matches2 = [e for e in events2 if e["uid"] == uid]
            assert len(matches2) == 1, (
                f"Event not found with stripped-Z timestamps: start={returned_start}, end={returned_end}"
            )
        finally:
            _delete_event_by_uid(uid)

    def test_update_then_read_back(self, connector):
        """Create → update → read back → verify only updated fields changed."""
        uid = _create_single_event(connector,
            calendar_name=TEST_CALENDAR,
            summary="Before Update",
            start_date="2027-04-01T09:00:00",
            end_date="2027-04-01T10:00:00",
            location="Room A",
        )
        try:
            _update_single_event(connector, TEST_CALENDAR, uid, summary="After Update")
            events = connector.get_events(TEST_CALENDAR, "2027-04-01", "2027-04-02")
            matches = [e for e in events if e["uid"] == uid]
            assert len(matches) == 1
            assert matches[0]["summary"] == "After Update"
            assert matches[0]["location"] == "Room A"  # unchanged
        finally:
            _delete_event_by_uid(uid)


class TestWorkflowIntegration:
    """Multi-step workflow tests simulating real Claude Desktop usage."""

    def test_full_event_lifecycle(self, connector):
        """Create → update → verify → delete → verify gone."""
        uid = _create_single_event(connector,
            calendar_name=TEST_CALENDAR,
            summary="Lifecycle Test",
            start_date="2027-05-01T10:00:00",
            end_date="2027-05-01T11:00:00",
        )
        try:
            # Update
            _update_single_event(connector, TEST_CALENDAR, uid, summary="Updated Lifecycle")

            # Verify update
            events = connector.get_events(TEST_CALENDAR, "2027-05-01", "2027-05-02")
            assert any(e["uid"] == uid and e["summary"] == "Updated Lifecycle" for e in events)

            # Delete
            result = connector.delete_events(TEST_CALENDAR, uid)
            assert uid in result["deleted_uids"]

            # Verify gone
            events = connector.get_events(TEST_CALENDAR, "2027-05-01", "2027-05-02")
            assert not any(e["uid"] == uid for e in events)
        finally:
            _delete_event_by_uid(uid)

    def test_availability_blocked_by_new_event(self, connector):
        """Check availability → create event → re-check → verify slot blocked."""
        # Check initial availability
        slots_before = connector.get_availability(
            [TEST_CALENDAR], "2027-06-01T09:00:00", "2027-06-01T12:00:00"
        )
        assert len(slots_before) == 1  # entirely free

        uid = _create_single_event(connector,
            calendar_name=TEST_CALENDAR,
            summary="Block This Slot",
            start_date="2027-06-01T10:00:00",
            end_date="2027-06-01T11:00:00",
        )
        try:
            # Re-check availability
            slots_after = connector.get_availability(
                [TEST_CALENDAR], "2027-06-01T09:00:00", "2027-06-01T12:00:00"
            )
            assert len(slots_after) == 2  # split into two free slots
            assert slots_after[0]["end_date"] == "2027-06-01T10:00:00"
            assert slots_after[1]["start_date"] == "2027-06-01T11:00:00"
        finally:
            _delete_event_by_uid(uid)


class TestTimezoneIntegration:
    """Timezone edge case tests."""

    def test_event_near_midnight(self, connector):
        """Event at 23:30 should be found when querying across midnight."""
        uid = _create_single_event(connector,
            calendar_name=TEST_CALENDAR,
            summary="Late Night Event",
            start_date="2027-07-01T23:30:00",
            end_date="2027-07-02T00:30:00",
        )
        try:
            events = connector.get_events(TEST_CALENDAR, "2027-07-01T23:00:00", "2027-07-02T01:00:00")
            matches = [e for e in events if e["uid"] == uid]
            assert len(matches) == 1
        finally:
            _delete_event_by_uid(uid)

    def test_allday_event_fields(self, connector):
        """All-day event should return allday_event=True with inclusive end_date."""
        uid = _create_single_event(connector,
            calendar_name=TEST_CALENDAR,
            summary="All Day Test",
            start_date="2027-08-01",
            end_date="2027-08-01",
            allday_event=True,
        )
        try:
            events = connector.get_events(TEST_CALENDAR, "2027-08-01", "2027-08-03")
            matches = [e for e in events if e["uid"] == uid]
            assert len(matches) == 1
            assert matches[0]["allday_event"] is True
            assert "2027-08-01" in matches[0]["end_date"]
        finally:
            _delete_event_by_uid(uid)


class TestErrorHandlingIntegration:
    """Error handling tests against real Calendar.app."""

    def test_get_events_nonexistent_calendar(self, connector):
        """Querying a non-existent calendar should raise ValueError."""
        with pytest.raises(ValueError, match="not found"):
            connector.get_events("Calendar-That-Does-Not-Exist", "2027-01-01", "2027-01-02")

    def test_delete_nonexistent_uid_reports_not_found(self, connector):
        """Deleting a non-existent UID should report it, not crash."""
        result = connector.delete_events(TEST_CALENDAR, "DOES-NOT-EXIST-UID-12345")
        assert result["deleted_uids"] == []
        assert "DOES-NOT-EXIST-UID-12345" in result["not_found_uids"]


class TestSpecialCharactersIntegration:
    """Integration tests for special characters in event fields."""

    def test_create_events_with_special_characters(self, connector):
        """Event titles with colons, slashes, apostrophes, and parentheses should round-trip."""
        title = "Lunch w/ John O'Brien: Planning (Q2/Q3)"
        uid = _create_single_event(connector,
            calendar_name=TEST_CALENDAR,
            summary=title,
            start_date="2027-11-01T12:00:00",
            end_date="2027-11-01T13:00:00",
        )
        try:
            events = connector.get_events(TEST_CALENDAR, "2027-11-01", "2027-11-02")
            matches = [e for e in events if e["uid"] == uid]
            assert len(matches) == 1
            assert matches[0]["summary"] == title
        finally:
            _delete_event_by_uid(uid)


class TestAlertsIntegration:
    """Integration tests for event alerts/reminders."""

    def test_create_events_with_multiple_alerts(self, connector):
        """Creating an event with multiple alerts should preserve all of them."""
        uid = _create_single_event(connector,
            calendar_name=TEST_CALENDAR,
            summary="Multi Alert Test",
            start_date="2027-11-05T10:00:00",
            end_date="2027-11-05T11:00:00",
            alert_minutes=[0, 15, 30, 60],
        )
        try:
            events = connector.get_events(TEST_CALENDAR, "2027-11-05", "2027-11-06")
            matches = [e for e in events if e["uid"] == uid]
            assert len(matches) == 1
            alerts = matches[0].get("alerts", [])
            alert_values = sorted([a["minutes_before"] for a in alerts])
            assert alert_values == [0, 15, 30, 60], (
                f"Expected alerts [0, 15, 30, 60], got {alert_values}"
            )
        finally:
            _delete_event_by_uid(uid)

    def test_alert_at_zero_minutes(self, connector):
        """Alert at 0 minutes (at time of event) should not be dropped as falsy."""
        uid = _create_single_event(connector,
            calendar_name=TEST_CALENDAR,
            summary="Zero Alert Test",
            start_date="2027-11-06T10:00:00",
            end_date="2027-11-06T11:00:00",
            alert_minutes=[0],
        )
        try:
            events = connector.get_events(TEST_CALENDAR, "2027-11-06", "2027-11-07")
            matches = [e for e in events if e["uid"] == uid]
            assert len(matches) == 1
            alerts = matches[0].get("alerts", [])
            assert len(alerts) == 1, f"Expected 1 alert, got {len(alerts)}"
            assert alerts[0]["minutes_before"] == 0
        finally:
            _delete_event_by_uid(uid)


class TestSearchEventsIntegration:
    """Integration tests for search_events."""

    def test_search_events_multi_month(self, connector):
        """Keyword search across a multi-month range should find a matching event."""
        keyword = f"UniqueSearch{uuid.uuid4().hex[:8]}"
        uid = _create_single_event(connector,
            calendar_name=TEST_CALENDAR,
            summary=f"Meeting about {keyword}",
            start_date="2027-12-15T10:00:00",
            end_date="2027-12-15T11:00:00",
        )
        try:
            results = connector.search_events(
                query=keyword,
                calendar_name=TEST_CALENDAR,
                start_date="2027-10-01",
                end_date="2028-04-01",
            )
            assert len(results) >= 1, f"Expected to find event with keyword '{keyword}'"
            assert any(keyword in e["summary"] for e in results)
        finally:
            _delete_event_by_uid(uid)


class TestAmbiguousCalendarIntegration:
    """Integration tests for ambiguous calendar name rejection (#212)."""

    DUPLICATE_NAME = "MCP-Test-Calendar"  # Same name as the session-scoped test calendar

    def _get_sources_for_name(self, connector, name):
        """Return list of sources for calendars with the given name."""
        calendars = connector.get_calendars()
        return [c["source"] for c in calendars if c["name"] == name]

    def test_ambiguous_calendar_rejects_create_without_source(self, connector):
        """create_events fails when duplicate calendar names exist and no source given."""
        from apple_calendar_mcp.calendar_connector import run_swift_helper

        # The session fixture already created MCP-Test-Calendar.
        # Create another with the same name — EventKit allows duplicates.
        run_swift_helper("create_calendar", ["--name", self.DUPLICATE_NAME])
        try:
            # Verify we actually have duplicates
            sources = self._get_sources_for_name(connector, self.DUPLICATE_NAME)
            assert len(sources) >= 2, f"Expected duplicates, got sources: {sources}"

            # create_events without source should fail with ambiguous_calendar
            events = [{"summary": "Ambiguity Test", "start_date": "2026-06-01T10:00:00", "end_date": "2026-06-01T11:00:00"}]
            with pytest.raises(ValueError, match="Multiple calendars"):
                connector.create_events(
                    calendar_name=self.DUPLICATE_NAME,
                    events=events,
                )
        finally:
            # Delete one duplicate — after that, the name is unambiguous again.
            # Use source to target the one we just created.
            sources = self._get_sources_for_name(connector, self.DUPLICATE_NAME)
            if len(sources) >= 2:
                # Delete with source to target the right one
                try:
                    run_swift_helper(
                        "delete_calendar",
                        ["--name", self.DUPLICATE_NAME, "--source", sources[-1]],
                    )
                except Exception:
                    # Fallback: if still ambiguous after source, try each source
                    for source in sources[1:]:
                        try:
                            run_swift_helper(
                                "delete_calendar",
                                ["--name", self.DUPLICATE_NAME, "--source", source],
                            )
                            break
                        except Exception:
                            pass


# ── get_conflicts ──────────────────────────────────────────────────────────


class TestGetConflictsIntegration:
    """Integration tests for get_conflicts."""

    def test_overlapping_events_detected(self, connector):
        """Two overlapping events should produce a conflict."""
        tag = uuid.uuid4().hex[:8]
        uid1 = _create_single_event(
            connector, TEST_CALENDAR, f"Conflict-A-{tag}",
            "2028-09-15T10:00:00", "2028-09-15T11:00:00",
        )
        uid2 = _create_single_event(
            connector, TEST_CALENDAR, f"Conflict-B-{tag}",
            "2028-09-15T10:30:00", "2028-09-15T11:30:00",
        )
        try:
            conflicts = connector.get_conflicts(
                [TEST_CALENDAR], "2028-09-15T00:00:00", "2028-09-16T00:00:00"
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

    def test_adjacent_events_no_conflict(self, connector):
        """Two adjacent (non-overlapping) events should produce no conflict."""
        tag = uuid.uuid4().hex[:8]
        uid1 = _create_single_event(
            connector, TEST_CALENDAR, f"Adjacent-A-{tag}",
            "2028-09-16T10:00:00", "2028-09-16T11:00:00",
        )
        uid2 = _create_single_event(
            connector, TEST_CALENDAR, f"Adjacent-B-{tag}",
            "2028-09-16T11:00:00", "2028-09-16T12:00:00",
        )
        try:
            conflicts = connector.get_conflicts(
                [TEST_CALENDAR], "2028-09-16T00:00:00", "2028-09-17T00:00:00"
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

    def test_free_event_excluded_from_conflicts(self, connector):
        """An event marked availability='free' should not produce conflicts."""
        tag = uuid.uuid4().hex[:8]
        uid1 = _create_single_event(
            connector, TEST_CALENDAR, f"Busy-{tag}",
            "2028-09-17T10:00:00", "2028-09-17T11:00:00",
        )
        uid2 = _create_single_event(
            connector, TEST_CALENDAR, f"Free-{tag}",
            "2028-09-17T10:30:00", "2028-09-17T11:30:00",
            availability="free",
        )
        try:
            conflicts = connector.get_conflicts(
                [TEST_CALENDAR], "2028-09-17T00:00:00", "2028-09-18T00:00:00"
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

    def test_create_events_exceeds_batch_limit(self, connector):
        events = [{"summary": f"Event {i}", "start_date": "2026-06-15T10:00:00",
                    "end_date": "2026-06-15T11:00:00"} for i in range(51)]
        with pytest.raises(ValueError, match="exceeds limit of 50"):
            connector.create_events(TEST_CALENDAR, events)

    def test_update_events_exceeds_batch_limit(self, connector):
        updates = [{"uid": f"UID-{i}", "summary": f"Event {i}"} for i in range(51)]
        with pytest.raises(ValueError, match="exceeds limit of 50"):
            connector.update_events(TEST_CALENDAR, updates)

    def test_delete_events_exceeds_batch_limit(self, connector):
        uids = [f"UID-{i}" for i in range(51)]
        with pytest.raises(ValueError, match="exceeds limit of 50"):
            connector.delete_events(TEST_CALENDAR, uids)
