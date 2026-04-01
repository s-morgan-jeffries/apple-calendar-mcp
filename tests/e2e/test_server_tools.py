"""Tier 1 E2E tests — call @mcp.tool() functions directly through the server layer.

Tests the full path: tool function → JSON parsing → CalendarConnector → Swift → EventKit.
Requires CALENDAR_TEST_MODE=true and a test calendar in Calendar.app.
"""

import json
import os
from datetime import datetime, timedelta

import pytest

# Import tool functions directly from the server module
from apple_calendar_mcp.server_fastmcp import (
    create_events,
    delete_events,
    get_availability,
    get_calendars,
    get_conflicts,
    get_events,
    search_events,
    update_events,
)

pytestmark = [
    pytest.mark.e2e,
    pytest.mark.skipif(
        os.environ.get("CALENDAR_TEST_MODE") != "true",
        reason="E2E tests require CALENDAR_TEST_MODE=true",
    ),
]


def _future_date(years_ahead, month, day, time_suffix=""):
    """Generate a future date string to avoid conflicts with real events."""
    year = datetime.now().year + years_ahead
    base = f"{year}-{month:02d}-{day:02d}"
    return f"{base}T{time_suffix}" if time_suffix else base


class TestGetCalendarsE2E:
    """E2E tests for get_calendars through the server tool function."""

    def test_returns_formatted_string_with_calendar_id(self):
        """Output should include ID, Name, and Source fields."""
        result = get_calendars()
        assert isinstance(result, str)
        assert "ID:" in result
        assert "Name:" in result
        assert "Source:" in result

    def test_source_filter(self):
        """Filtering by source should return only matching calendars."""
        all_result = get_calendars()
        filtered_result = get_calendars(calendar_source="iCloud")
        # Filtered should be subset (fewer or equal calendars)
        assert len(filtered_result) <= len(all_result)
        if "iCloud" in all_result:
            assert "iCloud" in filtered_result


class TestCreateAndReadE2E:
    """E2E tests for creating and reading events through server tools."""

    def test_create_and_read_event_round_trip(self, test_calendar_id, cleanup_uids):
        """Create an event via tool, read back via get_events, verify fields match."""
        start = _future_date(6, 1, 15, "10:00:00")
        end = _future_date(6, 1, 15, "11:00:00")
        event = {
            "summary": "E2E Round Trip Test",
            "start_date": start,
            "end_date": end,
            "location": "Test Room",
            "notes": "Created by e2e test",
        }
        result = create_events(calendar_id=test_calendar_id, events=json.dumps([event]))
        assert "Created 1 event(s)" in result
        assert "E2E Round Trip Test" in result

        # Extract UID from result
        uid_line = [l for l in result.split("\n") if "UID:" in l][0]
        uid = uid_line.split("UID: ")[1].strip().rstrip(")")
        cleanup_uids.append(uid)

        # Read back
        events_result = get_events(
            calendar_ids=[test_calendar_id],
            start_date=_future_date(6, 1, 15),
            end_date=_future_date(6, 1, 15),
        )
        assert "E2E Round Trip Test" in events_result
        assert "Test Room" in events_result

    def test_create_events_invalid_json(self):
        """Malformed JSON should return an error string, not raise."""
        result = create_events(events="not valid json")
        assert "Error" in result
        assert "invalid JSON" in result

    def test_create_events_not_array(self):
        """Non-array JSON should return an error string."""
        result = create_events(events='{"summary": "test"}')
        assert "Error" in result
        assert "must be a JSON array" in result


class TestUpdateE2E:
    """E2E tests for updating events through the server tool."""

    def test_update_event_title(self, test_calendar_id, cleanup_uids):
        """Update an event's title via the tool and verify the change."""
        start = _future_date(6, 2, 10, "14:00:00")
        end = _future_date(6, 2, 10, "15:00:00")
        event = {"summary": "Before Update", "start_date": start, "end_date": end}
        create_result = create_events(calendar_id=test_calendar_id, events=json.dumps([event]))
        uid_line = [l for l in create_result.split("\n") if "UID:" in l][0]
        uid = uid_line.split("UID: ")[1].strip().rstrip(")")
        cleanup_uids.append(uid)

        # Update title
        update = [{"uid": uid, "summary": "After Update"}]
        update_result = update_events(calendar_id=test_calendar_id, updates=json.dumps(update))
        assert "Updated 1 event(s)" in update_result
        assert "summary" in update_result

        # Verify
        events_result = get_events(
            calendar_ids=[test_calendar_id],
            start_date=_future_date(6, 2, 10),
            end_date=_future_date(6, 2, 10),
        )
        assert "After Update" in events_result


class TestDeleteE2E:
    """E2E tests for deleting events through the server tool."""

    def test_delete_event(self, test_calendar_id):
        """Delete an event via the tool and verify it's gone."""
        start = _future_date(6, 3, 5, "09:00:00")
        end = _future_date(6, 3, 5, "10:00:00")
        event = {"summary": "Delete Me E2E", "start_date": start, "end_date": end}
        create_result = create_events(calendar_id=test_calendar_id, events=json.dumps([event]))
        uid_line = [l for l in create_result.split("\n") if "UID:" in l][0]
        uid = uid_line.split("UID: ")[1].strip().rstrip(")")

        # Delete
        delete_result = delete_events(calendar_id=test_calendar_id, event_uids=uid)
        assert "Deleted 1 event(s)" in delete_result

        # Verify gone
        events_result = get_events(
            calendar_ids=[test_calendar_id],
            start_date=_future_date(6, 3, 5),
            end_date=_future_date(6, 3, 5),
        )
        assert "Delete Me E2E" not in events_result


class TestSearchE2E:
    """E2E tests for searching events through the server tool."""

    def test_search_finds_event(self, test_calendar_id, cleanup_uids):
        """Search by text should find a matching event."""
        start = _future_date(6, 4, 1, "11:00:00")
        end = _future_date(6, 4, 1, "12:00:00")
        event = {"summary": "UniqueSearchTermXYZ", "start_date": start, "end_date": end}
        create_result = create_events(calendar_id=test_calendar_id, events=json.dumps([event]))
        uid_line = [l for l in create_result.split("\n") if "UID:" in l][0]
        uid = uid_line.split("UID: ")[1].strip().rstrip(")")
        cleanup_uids.append(uid)

        result = search_events(query="UniqueSearchTermXYZ", calendar_ids=[test_calendar_id])
        assert "UniqueSearchTermXYZ" in result


class TestAvailabilityE2E:
    """E2E tests for availability checking through the server tool."""

    def test_availability_around_event(self, test_calendar_id, cleanup_uids):
        """Event should block availability in its time slot."""
        date = _future_date(6, 5, 1)
        start = f"{date}T10:00:00"
        end = f"{date}T11:00:00"
        event = {"summary": "Busy Block E2E", "start_date": start, "end_date": end}
        create_result = create_events(calendar_id=test_calendar_id, events=json.dumps([event]))
        uid_line = [l for l in create_result.split("\n") if "UID:" in l][0]
        uid = uid_line.split("UID: ")[1].strip().rstrip(")")
        cleanup_uids.append(uid)

        result = get_availability(
            calendar_ids=[test_calendar_id],
            start_date=f"{date}T09:00:00",
            end_date=f"{date}T12:00:00",
        )
        assert "free slot" in result.lower() or "Free" in result


class TestConflictsE2E:
    """E2E tests for conflict detection through the server tool."""

    def test_overlapping_events_detected(self, test_calendar_id, cleanup_uids):
        """Two overlapping events should be reported as a conflict."""
        date = _future_date(6, 6, 1)
        event_a = {"summary": "Conflict A E2E", "start_date": f"{date}T10:00:00", "end_date": f"{date}T11:30:00"}
        event_b = {"summary": "Conflict B E2E", "start_date": f"{date}T11:00:00", "end_date": f"{date}T12:00:00"}

        result_a = create_events(calendar_id=test_calendar_id, events=json.dumps([event_a]))
        uid_a = [l for l in result_a.split("\n") if "UID:" in l][0].split("UID: ")[1].strip().rstrip(")")
        cleanup_uids.append(uid_a)

        result_b = create_events(calendar_id=test_calendar_id, events=json.dumps([event_b]))
        uid_b = [l for l in result_b.split("\n") if "UID:" in l][0].split("UID: ")[1].strip().rstrip(")")
        cleanup_uids.append(uid_b)

        conflicts = get_conflicts(
            calendar_ids=[test_calendar_id],
            start_date=f"{date}T00:00:00",
            end_date=f"{date}T23:59:59",
        )
        assert "conflict" in conflicts.lower() or "overlap" in conflicts.lower()
