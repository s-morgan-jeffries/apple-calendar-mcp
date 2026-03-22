"""Unit tests for the FastMCP server layer."""
import json
import os
from unittest.mock import patch, MagicMock

import pytest

from apple_calendar_mcp.server_fastmcp import mcp, get_client


class TestGetClient:
    """Tests for the lazy client initialization."""

    def test_returns_calendar_connector(self):
        from apple_calendar_mcp.calendar_connector import CalendarConnector
        client = get_client()
        assert isinstance(client, CalendarConnector)

    def test_returns_same_instance(self):
        """Singleton pattern — same client on repeated calls."""
        client1 = get_client()
        client2 = get_client()
        assert client1 is client2


class TestProductionConfig:
    """Tests for safety check configuration based on environment."""

    def setup_method(self):
        # Reset the singleton so each test gets a fresh client
        import apple_calendar_mcp.server_fastmcp as mod
        self._original_client = mod._client
        mod._client = None

    def teardown_method(self):
        import apple_calendar_mcp.server_fastmcp as mod
        mod._client = self._original_client

    def test_safety_checks_disabled_without_test_mode(self):
        """In production (no CALENDAR_TEST_MODE), safety checks should be off."""
        env = os.environ.copy()
        env.pop("CALENDAR_TEST_MODE", None)
        with patch.dict(os.environ, env, clear=True):
            client = get_client()
            assert client.enable_safety_checks is False

    def test_safety_checks_enabled_with_test_mode(self):
        """In test mode (CALENDAR_TEST_MODE=true), safety checks should be on."""
        with patch.dict(os.environ, {"CALENDAR_TEST_MODE": "true"}):
            client = get_client()
            assert client.enable_safety_checks is True


class TestGetCalendarsTool:
    """Tests for the get_calendars MCP tool."""

    @patch("apple_calendar_mcp.server_fastmcp.get_client")
    def test_returns_formatted_calendar_list(self, mock_get_client):
        mock_client = MagicMock()
        mock_client.get_calendars.return_value = [
            {"name": "Personal", "writable": True, "description": "", "color": "#0072FF", "source": "iCloud"},
            {"name": "Work", "writable": True, "description": "", "color": "#FF0023", "source": "Google"},
        ]
        mock_get_client.return_value = mock_client

        # Import the tool function
        from apple_calendar_mcp.server_fastmcp import get_calendars
        result = get_calendars()

        assert "Personal" in result
        assert "Work" in result

    @patch("apple_calendar_mcp.server_fastmcp.get_client")
    def test_returns_string(self, mock_get_client):
        mock_client = MagicMock()
        mock_client.get_calendars.return_value = [
            {"name": "Test", "writable": True, "description": "", "color": "#000000", "source": "iCloud"},
        ]
        mock_get_client.return_value = mock_client

        from apple_calendar_mcp.server_fastmcp import get_calendars
        result = get_calendars()
        assert isinstance(result, str)

    @patch("apple_calendar_mcp.server_fastmcp.get_client")
    def test_empty_calendars(self, mock_get_client):
        mock_client = MagicMock()
        mock_client.get_calendars.return_value = []
        mock_get_client.return_value = mock_client

        from apple_calendar_mcp.server_fastmcp import get_calendars
        result = get_calendars()
        assert "No calendars found" in result


class TestCreateCalendarTool:
    """Tests for the create_calendar MCP tool."""

    @patch("apple_calendar_mcp.server_fastmcp.get_client")
    def test_returns_success_message(self, mock_get_client):
        mock_client = MagicMock()
        mock_client.create_calendar.return_value = {"name": "New Calendar"}
        mock_get_client.return_value = mock_client

        from apple_calendar_mcp.server_fastmcp import create_calendar
        result = create_calendar(name="New Calendar")
        assert "Created calendar" in result
        assert "New Calendar" in result

    @patch("apple_calendar_mcp.server_fastmcp.get_client")
    def test_returns_error_on_failure(self, mock_get_client):
        mock_client = MagicMock()
        mock_client.create_calendar.side_effect = Exception("AppleScript failed")
        mock_get_client.return_value = mock_client

        from apple_calendar_mcp.server_fastmcp import create_calendar
        result = create_calendar(name="Bad Calendar")
        assert "Error" in result
        assert isinstance(result, str)


class TestDeleteCalendarTool:
    """Tests for the delete_calendar MCP tool."""

    @patch("apple_calendar_mcp.server_fastmcp.get_client")
    def test_returns_success_message(self, mock_get_client):
        mock_client = MagicMock()
        mock_client.delete_calendar.return_value = {"name": "Old Calendar"}
        mock_get_client.return_value = mock_client

        from apple_calendar_mcp.server_fastmcp import delete_calendar
        result = delete_calendar(name="Old Calendar")
        assert "Deleted calendar" in result
        assert "Old Calendar" in result

    @patch("apple_calendar_mcp.server_fastmcp.get_client")
    def test_returns_error_on_failure(self, mock_get_client):
        mock_client = MagicMock()
        mock_client.delete_calendar.side_effect = ValueError("Calendar 'X' not found")
        mock_get_client.return_value = mock_client

        from apple_calendar_mcp.server_fastmcp import delete_calendar
        result = delete_calendar(name="X")
        assert "Error" in result
        assert isinstance(result, str)


class TestGetEventsTool:
    """Tests for the get_events MCP tool."""

    @patch("apple_calendar_mcp.server_fastmcp.get_client")
    def test_returns_formatted_event_list(self, mock_get_client):
        mock_client = MagicMock()
        mock_client.get_events.return_value = [
            {"uid": "ABC-123", "summary": "Team Meeting", "start_date": "2026-03-15T14:00:00",
             "end_date": "2026-03-15T15:00:00", "allday_event": False, "location": "Room 4",
             "notes": "Weekly sync", "url": "", "status": "confirmed", "calendar_name": "Work"},
        ]
        mock_get_client.return_value = mock_client

        from apple_calendar_mcp.server_fastmcp import get_events
        result = get_events(calendar_name="Work", start_date="2026-03-15T00:00:00", end_date="2026-03-16T00:00:00")
        assert "Team Meeting" in result
        assert "Room 4" in result
        assert isinstance(result, str)

    @patch("apple_calendar_mcp.server_fastmcp.get_client")
    def test_formats_recurring_event(self, mock_get_client):
        mock_client = MagicMock()
        mock_client.get_events.return_value = [
            {"uid": "REC-123", "summary": "Weekly Standup", "start_date": "2026-07-01T09:00:00",
             "end_date": "2026-07-01T09:30:00", "allday_event": False, "location": "",
             "notes": "", "url": "", "status": "confirmed", "calendar_name": "Work",
             "is_recurring": True, "recurrence_rule": "FREQ=WEEKLY;INTERVAL=1;BYDAY=MO,WE,FR",
             "is_detached": False, "occurrence_date": "2026-07-01T09:00:00"},
        ]
        mock_get_client.return_value = mock_client

        from apple_calendar_mcp.server_fastmcp import get_events
        result = get_events(calendar_name="Work", start_date="2026-07-01", end_date="2026-07-02")
        assert "Recurring" in result
        assert "FREQ=WEEKLY" in result

    @patch("apple_calendar_mcp.server_fastmcp.get_client")
    def test_formats_attendees(self, mock_get_client):
        mock_client = MagicMock()
        mock_client.get_events.return_value = [
            {"uid": "ATT-123", "summary": "Team Meeting", "start_date": "2026-07-01T14:00:00",
             "end_date": "2026-07-01T15:00:00", "allday_event": False, "location": "",
             "notes": "", "url": "", "status": "confirmed", "calendar_name": "Work",
             "attendees": [
                 {"name": "Alice", "email": "alice@example.com", "role": "required", "status": "accepted"},
                 {"name": "", "email": "bob@example.com", "role": "optional", "status": "pending"},
             ]},
        ]
        mock_get_client.return_value = mock_client

        from apple_calendar_mcp.server_fastmcp import get_events
        result = get_events(calendar_name="Work", start_date="2026-07-01", end_date="2026-07-02")
        assert "Attendees (2)" in result
        assert "Alice" in result
        assert "bob@example.com" in result

    @patch("apple_calendar_mcp.server_fastmcp.get_client")
    def test_returns_no_events_message(self, mock_get_client):
        mock_client = MagicMock()
        mock_client.get_events.return_value = []
        mock_get_client.return_value = mock_client

        from apple_calendar_mcp.server_fastmcp import get_events
        result = get_events(calendar_name="Work", start_date="2026-03-15T00:00:00", end_date="2026-03-16T00:00:00")
        assert "No events found" in result

    @patch("apple_calendar_mcp.server_fastmcp.get_client")
    def test_returns_error_string_on_failure(self, mock_get_client):
        mock_client = MagicMock()
        mock_client.get_events.side_effect = ValueError("Calendar 'Foo' not found")
        mock_get_client.return_value = mock_client

        from apple_calendar_mcp.server_fastmcp import get_events
        result = get_events(calendar_name="Foo", start_date="2026-03-15T00:00:00", end_date="2026-03-16T00:00:00")
        assert "Error" in result
        assert isinstance(result, str)

    @patch("apple_calendar_mcp.server_fastmcp.get_client")
    def test_returns_permission_error_as_string(self, mock_get_client):
        mock_client = MagicMock()
        mock_client.get_events.side_effect = PermissionError("Calendar access denied")
        mock_get_client.return_value = mock_client

        from apple_calendar_mcp.server_fastmcp import get_events
        result = get_events(calendar_name="Work", start_date="2026-03-15T00:00:00", end_date="2026-03-16T00:00:00")
        assert "Error" in result


class TestGetAvailabilityTool:
    """Tests for the get_availability MCP tool."""

    @patch("apple_calendar_mcp.server_fastmcp.get_client")
    def test_returns_formatted_free_slots(self, mock_get_client):
        mock_client = MagicMock()
        mock_client.get_availability.return_value = [
            {"start_date": "2026-03-15T09:00:00", "end_date": "2026-03-15T10:00:00", "duration_minutes": 60},
            {"start_date": "2026-03-15T11:00:00", "end_date": "2026-03-15T13:00:00", "duration_minutes": 120},
        ]
        mock_get_client.return_value = mock_client

        from apple_calendar_mcp.server_fastmcp import get_availability
        result = get_availability(calendar_names=["Work"], start_date="2026-03-15T09:00:00", end_date="2026-03-15T17:00:00")
        assert "2 free slot(s)" in result
        assert "1h" in result
        assert "2h" in result
        assert isinstance(result, str)

    @patch("apple_calendar_mcp.server_fastmcp.get_client")
    def test_returns_no_free_time_message(self, mock_get_client):
        mock_client = MagicMock()
        mock_client.get_availability.return_value = []
        mock_get_client.return_value = mock_client

        from apple_calendar_mcp.server_fastmcp import get_availability
        result = get_availability(calendar_names=["Work"], start_date="2026-03-15T09:00:00", end_date="2026-03-15T17:00:00")
        assert "No free time" in result

    @patch("apple_calendar_mcp.server_fastmcp.get_client")
    def test_returns_error_string_on_failure(self, mock_get_client):
        mock_client = MagicMock()
        mock_client.get_availability.side_effect = ValueError("Calendar 'Foo' not found")
        mock_get_client.return_value = mock_client

        from apple_calendar_mcp.server_fastmcp import get_availability
        result = get_availability(calendar_names=["Foo"], start_date="2026-03-15T09:00:00", end_date="2026-03-15T17:00:00")
        assert "Error" in result
        assert isinstance(result, str)

    @patch("apple_calendar_mcp.server_fastmcp.get_client")
    def test_passes_calendar_names_list(self, mock_get_client):
        mock_client = MagicMock()
        mock_client.get_availability.return_value = []
        mock_get_client.return_value = mock_client

        from apple_calendar_mcp.server_fastmcp import get_availability
        get_availability(calendar_names=["Work", "Personal"], start_date="2026-03-15T09:00:00", end_date="2026-03-15T17:00:00")
        mock_client.get_availability.assert_called_once_with(
            calendar_names=["Work", "Personal"],
            start_date="2026-03-15T09:00:00",
            end_date="2026-03-15T17:00:00",
            min_duration_minutes=None,
            working_hours_start=None,
            working_hours_end=None,
        )

    @patch("apple_calendar_mcp.server_fastmcp.get_client")
    def test_formats_duration_hours_and_minutes(self, mock_get_client):
        mock_client = MagicMock()
        mock_client.get_availability.return_value = [
            {"start_date": "2026-03-15T09:00:00", "end_date": "2026-03-15T10:30:00", "duration_minutes": 90},
        ]
        mock_get_client.return_value = mock_client

        from apple_calendar_mcp.server_fastmcp import get_availability
        result = get_availability(calendar_names=["Work"], start_date="2026-03-15T09:00:00", end_date="2026-03-15T17:00:00")
        assert "1h 30m" in result

    @patch("apple_calendar_mcp.server_fastmcp.get_client")
    def test_formats_duration_minutes_only(self, mock_get_client):
        mock_client = MagicMock()
        mock_client.get_availability.return_value = [
            {"start_date": "2026-03-15T09:00:00", "end_date": "2026-03-15T09:30:00", "duration_minutes": 30},
        ]
        mock_get_client.return_value = mock_client

        from apple_calendar_mcp.server_fastmcp import get_availability
        result = get_availability(calendar_names=["Work"], start_date="2026-03-15T09:00:00", end_date="2026-03-15T17:00:00")
        assert "30m" in result

    @patch("apple_calendar_mcp.server_fastmcp.get_client")
    def test_passes_filter_params_through(self, mock_get_client):
        mock_client = MagicMock()
        mock_client.get_availability.return_value = []
        mock_get_client.return_value = mock_client

        from apple_calendar_mcp.server_fastmcp import get_availability
        get_availability(
            calendar_names=["Work"],
            start_date="2026-03-15T09:00:00",
            end_date="2026-03-15T17:00:00",
            min_duration_minutes=45,
            working_hours_start="09:00",
            working_hours_end="17:00",
        )
        mock_client.get_availability.assert_called_once_with(
            calendar_names=["Work"],
            start_date="2026-03-15T09:00:00",
            end_date="2026-03-15T17:00:00",
            min_duration_minutes=45,
            working_hours_start="09:00",
            working_hours_end="17:00",
        )

    @patch("apple_calendar_mcp.server_fastmcp.get_client")
    def test_output_includes_filter_description(self, mock_get_client):
        mock_client = MagicMock()
        mock_client.get_availability.return_value = [
            {"start_date": "2026-03-15T09:00:00", "end_date": "2026-03-15T10:00:00", "duration_minutes": 60},
        ]
        mock_get_client.return_value = mock_client

        from apple_calendar_mcp.server_fastmcp import get_availability
        result = get_availability(
            calendar_names=["Work"],
            start_date="2026-03-15T09:00:00",
            end_date="2026-03-15T17:00:00",
            min_duration_minutes=45,
            working_hours_start="09:00",
            working_hours_end="17:00",
        )
        assert ">= 45 min" in result
        assert "09:00-17:00" in result

    @patch("apple_calendar_mcp.server_fastmcp.get_client")
    def test_no_filter_description_without_params(self, mock_get_client):
        mock_client = MagicMock()
        mock_client.get_availability.return_value = []
        mock_get_client.return_value = mock_client

        from apple_calendar_mcp.server_fastmcp import get_availability
        result = get_availability(
            calendar_names=["Work"],
            start_date="2026-03-15T09:00:00",
            end_date="2026-03-15T17:00:00",
        )
        assert ">=" not in result
        assert "09:00-17:00" not in result


class TestDeleteEventsTool:
    """Tests for the delete_events MCP tool."""

    @patch("apple_calendar_mcp.server_fastmcp.get_client")
    def test_returns_success_message(self, mock_get_client):
        mock_client = MagicMock()
        mock_client.delete_events.return_value = {
            "deleted_uids": ["ABC-123"],
            "not_found_uids": [],
        }
        mock_get_client.return_value = mock_client

        from apple_calendar_mcp.server_fastmcp import delete_events
        result = delete_events(calendar_name="Work", event_uid="ABC-123")
        assert "Deleted 1 event(s)" in result
        assert "Work" in result
        assert isinstance(result, str)

    @patch("apple_calendar_mcp.server_fastmcp.get_client")
    def test_returns_error_on_failure(self, mock_get_client):
        mock_client = MagicMock()
        mock_client.delete_events.side_effect = Exception("Calendar not found")
        mock_get_client.return_value = mock_client

        from apple_calendar_mcp.server_fastmcp import delete_events
        result = delete_events(calendar_name="Nonexistent", event_uid="ABC-123")
        assert "Error" in result
        assert isinstance(result, str)

    @patch("apple_calendar_mcp.server_fastmcp.get_client")
    def test_returns_partial_success_message(self, mock_get_client):
        mock_client = MagicMock()
        mock_client.delete_events.return_value = {
            "deleted_uids": ["UID-1", "UID-3"],
            "not_found_uids": ["UID-2"],
        }
        mock_get_client.return_value = mock_client

        from apple_calendar_mcp.server_fastmcp import delete_events
        result = delete_events(calendar_name="Work", event_uid=["UID-1", "UID-2", "UID-3"])
        assert "Deleted 2 event(s)" in result
        assert "not found" in result.lower() or "UID-2" in result

    @patch("apple_calendar_mcp.server_fastmcp.get_client")
    def test_accepts_list_of_uids(self, mock_get_client):
        mock_client = MagicMock()
        mock_client.delete_events.return_value = {
            "deleted_uids": ["UID-1", "UID-2"],
            "not_found_uids": [],
        }
        mock_get_client.return_value = mock_client

        from apple_calendar_mcp.server_fastmcp import delete_events
        delete_events(calendar_name="Work", event_uid=["UID-1", "UID-2"])
        mock_client.delete_events.assert_called_once_with(
            calendar_name="Work",
            event_uids=["UID-1", "UID-2"],
            span="this_event",
            occurrence_date=None,
        )


class TestServerConfiguration:
    """Tests for MCP server configuration."""

    def test_server_has_instructions(self):
        # The mcp server should have instructions set
        assert mcp.instructions is not None
        assert len(mcp.instructions) > 0

    def test_server_name(self):
        assert mcp.name == "apple-calendar-mcp"


class TestFormatCalendarDescription:
    """Tests for _format_calendar with description field."""

    def test_calendar_with_description(self):
        from apple_calendar_mcp.server_fastmcp import _format_calendar
        cal = {"name": "Work", "writable": True, "description": "My work calendar", "color": "#FF0000", "source": "iCloud"}
        result = _format_calendar(cal)
        assert "Description: My work calendar" in result
        assert "Source: iCloud" in result

    def test_calendar_without_description(self):
        from apple_calendar_mcp.server_fastmcp import _format_calendar
        cal = {"name": "Work", "writable": True, "description": "", "color": "#FF0000", "source": "Google"}
        result = _format_calendar(cal)
        assert "Description" not in result
        assert "Source: Google" in result


class TestFormatEventDetails:
    """Tests for _format_event_details, _format_alerts, and _format_recurrence."""

    def test_allday_event(self):
        from apple_calendar_mcp.server_fastmcp import _format_event_details
        event = {"allday_event": True}
        lines = _format_event_details(event)
        assert "All-day event" in lines

    def test_non_allday_event(self):
        from apple_calendar_mcp.server_fastmcp import _format_event_details
        event = {"allday_event": False}
        lines = _format_event_details(event)
        assert "All-day event" not in lines

    def test_availability_free(self):
        from apple_calendar_mcp.server_fastmcp import _format_event_details
        event = {"availability": "free"}
        lines = _format_event_details(event)
        assert "Availability: free" in lines

    def test_availability_busy_not_shown(self):
        from apple_calendar_mcp.server_fastmcp import _format_event_details
        event = {"availability": "busy"}
        lines = _format_event_details(event)
        assert all("Availability" not in line for line in lines)

    def test_format_alerts(self):
        from apple_calendar_mcp.server_fastmcp import _format_alerts
        alerts = [{"minutes_before": 15}, {"minutes_before": 60}]
        lines = _format_alerts(alerts)
        assert len(lines) == 1
        assert "15m before" in lines[0]
        assert "60m before" in lines[0]

    def test_format_alerts_empty(self):
        from apple_calendar_mcp.server_fastmcp import _format_alerts
        assert _format_alerts([]) == []

    def test_format_recurrence_not_recurring(self):
        from apple_calendar_mcp.server_fastmcp import _format_recurrence
        event = {"is_recurring": False}
        assert _format_recurrence(event) == []

    def test_format_recurrence_detached(self):
        from apple_calendar_mcp.server_fastmcp import _format_recurrence
        event = {"is_recurring": True, "recurrence_rule": "FREQ=DAILY", "is_detached": True}
        lines = _format_recurrence(event)
        assert any("detached" in line.lower() for line in lines)


class TestCreateEventsTool:
    """Tests for the create_events MCP tool (batch)."""

    @patch("apple_calendar_mcp.server_fastmcp.get_client")
    def test_batch_create_success(self, mock_get_client):
        mock_client = MagicMock()
        mock_client.create_events.return_value = {
            "created": [
                {"summary": "Event A", "uid": "UID-A"},
                {"summary": "Event B", "uid": "UID-B"},
            ],
            "errors": [],
        }
        mock_get_client.return_value = mock_client

        from apple_calendar_mcp.server_fastmcp import create_events
        events_json = json.dumps([
            {"summary": "Event A", "start_date": "2026-03-15T10:00:00", "end_date": "2026-03-15T11:00:00"},
            {"summary": "Event B", "start_date": "2026-03-15T12:00:00", "end_date": "2026-03-15T13:00:00"},
        ])
        result = create_events(calendar_name="Work", events=events_json)
        assert "Created 2 event(s)" in result
        assert "Event A" in result
        assert "UID-A" in result
        assert "Event B" in result
        assert isinstance(result, str)

    @patch("apple_calendar_mcp.server_fastmcp.get_client")
    def test_batch_create_error(self, mock_get_client):
        mock_client = MagicMock()
        mock_client.create_events.side_effect = Exception("Calendar not found")
        mock_get_client.return_value = mock_client

        from apple_calendar_mcp.server_fastmcp import create_events
        events_json = json.dumps([
            {"summary": "Event A", "start_date": "2026-03-15T10:00:00", "end_date": "2026-03-15T11:00:00"},
        ])
        result = create_events(calendar_name="Nonexistent", events=events_json)
        assert "Error" in result
        assert isinstance(result, str)

    @patch("apple_calendar_mcp.server_fastmcp.get_client")
    def test_batch_create_partial_success(self, mock_get_client):
        mock_client = MagicMock()
        mock_client.create_events.return_value = {
            "created": [{"summary": "Event A", "uid": "UID-A"}],
            "errors": [{"index": 1, "summary": "Event B", "error": "Invalid date"}],
        }
        mock_get_client.return_value = mock_client

        from apple_calendar_mcp.server_fastmcp import create_events
        events_json = json.dumps([
            {"summary": "Event A", "start_date": "2026-03-15T10:00:00", "end_date": "2026-03-15T11:00:00"},
            {"summary": "Event B", "start_date": "bad-date", "end_date": "bad-date"},
        ])
        result = create_events(calendar_name="Work", events=events_json)
        assert "Created 1 event(s)" in result
        assert "1 error(s)" in result
        assert "Invalid date" in result

    def test_invalid_json(self):
        from apple_calendar_mcp.server_fastmcp import create_events
        result = create_events(calendar_name="Work", events="not json")
        assert "Error" in result
        assert "invalid JSON" in result

    def test_non_array_json(self):
        from apple_calendar_mcp.server_fastmcp import create_events
        result = create_events(calendar_name="Work", events='{"summary": "test"}')
        assert "Error" in result
        assert "JSON array" in result


class TestUpdateEventsTool:
    """Tests for the update_events MCP tool (batch)."""

    @patch("apple_calendar_mcp.server_fastmcp.get_client")
    def test_batch_update_success(self, mock_get_client):
        mock_client = MagicMock()
        mock_client.update_events.return_value = {
            "updated": [
                {"summary": "Event A", "updated_fields": ["start_date", "end_date"]},
                {"summary": "Event B", "updated_fields": ["location"]},
            ],
            "errors": [],
        }
        mock_get_client.return_value = mock_client

        from apple_calendar_mcp.server_fastmcp import update_events
        updates_json = json.dumps([
            {"uid": "UID-A", "start_date": "2026-03-15T11:00:00", "end_date": "2026-03-15T12:00:00"},
            {"uid": "UID-B", "location": "Room B"},
        ])
        result = update_events(calendar_name="Work", updates=updates_json)
        assert "Updated 2 event(s)" in result
        assert "Event A" in result
        assert "start_date, end_date" in result
        assert "location" in result
        assert isinstance(result, str)

    @patch("apple_calendar_mcp.server_fastmcp.get_client")
    def test_batch_update_error(self, mock_get_client):
        mock_client = MagicMock()
        mock_client.update_events.side_effect = Exception("Calendar not found")
        mock_get_client.return_value = mock_client

        from apple_calendar_mcp.server_fastmcp import update_events
        updates_json = json.dumps([{"uid": "UID-A", "summary": "New"}])
        result = update_events(calendar_name="Nonexistent", updates=updates_json)
        assert "Error" in result
        assert isinstance(result, str)

    @patch("apple_calendar_mcp.server_fastmcp.get_client")
    def test_batch_update_partial_with_errors(self, mock_get_client):
        mock_client = MagicMock()
        mock_client.update_events.return_value = {
            "updated": [{"summary": "Event A", "updated_fields": ["summary"]}],
            "errors": [{"index": 1, "uid": "UID-B", "error": "Event not found"}],
        }
        mock_get_client.return_value = mock_client

        from apple_calendar_mcp.server_fastmcp import update_events
        updates_json = json.dumps([
            {"uid": "UID-A", "summary": "New A"},
            {"uid": "UID-B", "summary": "New B"},
        ])
        result = update_events(calendar_name="Work", updates=updates_json)
        assert "Updated 1 event(s)" in result
        assert "1 error(s)" in result
        assert "Event not found" in result

    def test_invalid_json(self):
        from apple_calendar_mcp.server_fastmcp import update_events
        result = update_events(calendar_name="Work", updates="not json")
        assert "Error" in result
        assert "invalid JSON" in result

    def test_non_array_json(self):
        from apple_calendar_mcp.server_fastmcp import update_events
        result = update_events(calendar_name="Work", updates='{"uid": "test"}')
        assert "Error" in result
        assert "JSON array" in result


class TestSearchEventsTool:
    """Tests for the search_events MCP tool."""

    @patch("apple_calendar_mcp.server_fastmcp.get_client")
    def test_search_with_results(self, mock_get_client):
        mock_client = MagicMock()
        mock_client.search_events.return_value = [
            {"uid": "S-123", "summary": "Team Standup", "start_date": "2026-03-15T09:00:00",
             "end_date": "2026-03-15T09:30:00", "allday_event": False, "location": "",
             "notes": "", "url": "", "status": "confirmed", "calendar_name": "Work"},
        ]
        mock_get_client.return_value = mock_client

        from apple_calendar_mcp.server_fastmcp import search_events
        result = search_events(query="standup", calendar_name="Work")
        assert "Found 1 event(s)" in result
        assert "Team Standup" in result
        assert "in 'Work'" in result
        assert isinstance(result, str)

    @patch("apple_calendar_mcp.server_fastmcp.get_client")
    def test_search_no_results_specific_calendar(self, mock_get_client):
        mock_client = MagicMock()
        mock_client.search_events.return_value = []
        mock_get_client.return_value = mock_client

        from apple_calendar_mcp.server_fastmcp import search_events
        result = search_events(query="nonexistent", calendar_name="Work")
        assert "No events matching" in result
        assert "in 'Work'" in result

    @patch("apple_calendar_mcp.server_fastmcp.get_client")
    def test_search_no_results_all_calendars(self, mock_get_client):
        mock_client = MagicMock()
        mock_client.search_events.return_value = []
        mock_get_client.return_value = mock_client

        from apple_calendar_mcp.server_fastmcp import search_events
        result = search_events(query="nonexistent")
        assert "No events matching" in result
        assert "across all calendars" in result

    @patch("apple_calendar_mcp.server_fastmcp.get_client")
    def test_search_error(self, mock_get_client):
        mock_client = MagicMock()
        mock_client.search_events.side_effect = Exception("Search failed")
        mock_get_client.return_value = mock_client

        from apple_calendar_mcp.server_fastmcp import search_events
        result = search_events(query="test")
        assert "Error" in result
        assert isinstance(result, str)

    @patch("apple_calendar_mcp.server_fastmcp.get_client")
    def test_search_passes_none_for_empty_optional_params(self, mock_get_client):
        mock_client = MagicMock()
        mock_client.search_events.return_value = []
        mock_get_client.return_value = mock_client

        from apple_calendar_mcp.server_fastmcp import search_events
        search_events(query="test")
        mock_client.search_events.assert_called_once_with(
            query="test",
            calendar_name=None,
            start_date=None,
            end_date=None,
        )

    @patch("apple_calendar_mcp.server_fastmcp.get_client")
    def test_search_results_across_all_calendars(self, mock_get_client):
        mock_client = MagicMock()
        mock_client.search_events.return_value = [
            {"uid": "S-1", "summary": "Lunch", "start_date": "2026-03-15T12:00:00",
             "end_date": "2026-03-15T13:00:00", "allday_event": False, "location": "",
             "notes": "", "url": "", "status": "confirmed", "calendar_name": "Personal"},
        ]
        mock_get_client.return_value = mock_client

        from apple_calendar_mcp.server_fastmcp import search_events
        result = search_events(query="lunch")
        assert "across all calendars" in result


class TestGetConflictsTool:
    """Tests for the get_conflicts MCP tool."""

    @patch("apple_calendar_mcp.server_fastmcp.get_client")
    def test_conflicts_found(self, mock_get_client):
        mock_client = MagicMock()
        mock_client.get_conflicts.return_value = [
            {
                "event_a": {"summary": "Meeting A", "calendar_name": "Work",
                            "start_date": "2026-03-15T10:00:00", "end_date": "2026-03-15T11:00:00"},
                "event_b": {"summary": "Meeting B", "calendar_name": "Work",
                            "start_date": "2026-03-15T10:30:00", "end_date": "2026-03-15T11:30:00"},
                "overlap_start": "2026-03-15T10:30:00",
                "overlap_end": "2026-03-15T11:00:00",
                "overlap_minutes": 30,
            }
        ]
        mock_get_client.return_value = mock_client

        from apple_calendar_mcp.server_fastmcp import get_conflicts
        result = get_conflicts(calendar_names=["Work"], start_date="2026-03-15T00:00:00", end_date="2026-03-16T00:00:00")
        assert "Found 1 conflict(s)" in result
        assert "Meeting A" in result
        assert "Meeting B" in result
        assert "30 min overlap" in result
        assert isinstance(result, str)

    @patch("apple_calendar_mcp.server_fastmcp.get_client")
    def test_no_conflicts(self, mock_get_client):
        mock_client = MagicMock()
        mock_client.get_conflicts.return_value = []
        mock_get_client.return_value = mock_client

        from apple_calendar_mcp.server_fastmcp import get_conflicts
        result = get_conflicts(calendar_names=["Work"], start_date="2026-03-15T00:00:00", end_date="2026-03-16T00:00:00")
        assert "No conflicts found" in result

    @patch("apple_calendar_mcp.server_fastmcp.get_client")
    def test_conflicts_error(self, mock_get_client):
        mock_client = MagicMock()
        mock_client.get_conflicts.side_effect = Exception("Calendar not found")
        mock_get_client.return_value = mock_client

        from apple_calendar_mcp.server_fastmcp import get_conflicts
        result = get_conflicts(calendar_names=["Bad"], start_date="2026-03-15T00:00:00", end_date="2026-03-16T00:00:00")
        assert "Error" in result
        assert isinstance(result, str)


class TestDeleteEventsToolBranches:
    """Tests for uncovered branches in the delete_events tool."""

    @patch("apple_calendar_mcp.server_fastmcp.get_client")
    def test_single_uid_string_passed_directly(self, mock_get_client):
        mock_client = MagicMock()
        mock_client.delete_events.return_value = {
            "deleted_uids": ["UID-1"],
            "not_found_uids": [],
        }
        mock_get_client.return_value = mock_client

        from apple_calendar_mcp.server_fastmcp import delete_events
        result = delete_events(calendar_name="Work", event_uid="UID-1")
        # event_uid is passed as-is (string) to event_uids
        mock_client.delete_events.assert_called_once_with(
            calendar_name="Work",
            event_uids="UID-1",
            span="this_event",
            occurrence_date=None,
        )
        assert "Deleted 1 event(s)" in result

    @patch("apple_calendar_mcp.server_fastmcp.get_client")
    def test_occurrence_date_and_span_passed(self, mock_get_client):
        mock_client = MagicMock()
        mock_client.delete_events.return_value = {
            "deleted_uids": ["UID-1"],
            "not_found_uids": [],
        }
        mock_get_client.return_value = mock_client

        from apple_calendar_mcp.server_fastmcp import delete_events
        delete_events(
            calendar_name="Work", event_uid="UID-1",
            span="future_events",
            occurrence_date="2026-03-15T09:00:00",
        )
        call_kwargs = mock_client.delete_events.call_args[1]
        assert call_kwargs["span"] == "future_events"
        assert call_kwargs["occurrence_date"] == "2026-03-15T09:00:00"

    @patch("apple_calendar_mcp.server_fastmcp.get_client")
    def test_not_found_uids_reported(self, mock_get_client):
        mock_client = MagicMock()
        mock_client.delete_events.return_value = {
            "deleted_uids": [],
            "not_found_uids": ["UID-GONE"],
        }
        mock_get_client.return_value = mock_client

        from apple_calendar_mcp.server_fastmcp import delete_events
        result = delete_events(calendar_name="Work", event_uid="UID-GONE")
        assert "Deleted 0 event(s)" in result
        assert "Not found" in result
        assert "UID-GONE" in result
