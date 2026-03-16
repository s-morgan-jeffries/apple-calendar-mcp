"""Unit tests for the FastMCP server layer."""
import json
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


class TestGetCalendarsTool:
    """Tests for the get_calendars MCP tool."""

    @patch("apple_calendar_mcp.server_fastmcp.get_client")
    def test_returns_formatted_calendar_list(self, mock_get_client):
        mock_client = MagicMock()
        mock_client.get_calendars.return_value = [
            {"name": "Personal", "writable": True, "description": "", "color": "#0072FF"},
            {"name": "Work", "writable": True, "description": "", "color": "#FF0023"},
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
            {"name": "Test", "writable": True, "description": "", "color": "#000000"},
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


class TestCreateEventTool:
    """Tests for the create_event MCP tool."""

    @patch("apple_calendar_mcp.server_fastmcp.get_client")
    def test_returns_success_message_with_uid(self, mock_get_client):
        mock_client = MagicMock()
        mock_client.create_event.return_value = "3290DD8F-17E9-4DCC-B5FA-764655253E7A"
        mock_get_client.return_value = mock_client

        from apple_calendar_mcp.server_fastmcp import create_event
        result = create_event(
            calendar_name="MCP-Test-Calendar",
            summary="Team Meeting",
            start_date="2026-03-15T14:00:00",
            end_date="2026-03-15T15:00:00",
        )
        assert "Team Meeting" in result
        assert "3290DD8F-17E9-4DCC-B5FA-764655253E7A" in result
        assert "MCP-Test-Calendar" in result

    @patch("apple_calendar_mcp.server_fastmcp.get_client")
    def test_returns_error_string_on_failure(self, mock_get_client):
        mock_client = MagicMock()
        mock_client.create_event.side_effect = Exception("Calendar not found")
        mock_get_client.return_value = mock_client

        from apple_calendar_mcp.server_fastmcp import create_event
        result = create_event(
            calendar_name="Nonexistent",
            summary="Test",
            start_date="2026-03-15T14:00:00",
            end_date="2026-03-15T15:00:00",
        )
        assert "Error" in result
        assert isinstance(result, str)

    @patch("apple_calendar_mcp.server_fastmcp.get_client")
    def test_passes_optional_fields_to_connector(self, mock_get_client):
        mock_client = MagicMock()
        mock_client.create_event.return_value = "UID-123"
        mock_get_client.return_value = mock_client

        from apple_calendar_mcp.server_fastmcp import create_event
        create_event(
            calendar_name="MCP-Test-Calendar",
            summary="Lunch",
            start_date="2026-03-15T12:00:00",
            end_date="2026-03-15T13:00:00",
            location="Room A",
            description="Notes here",
            url="https://example.com",
            allday_event=True,
        )
        mock_client.create_event.assert_called_once_with(
            calendar_name="MCP-Test-Calendar",
            summary="Lunch",
            start_date="2026-03-15T12:00:00",
            end_date="2026-03-15T13:00:00",
            location="Room A",
            description="Notes here",
            url="https://example.com",
            allday_event=True,
        )

    @patch("apple_calendar_mcp.server_fastmcp.get_client")
    def test_returns_safety_error_as_string(self, mock_get_client):
        from apple_calendar_mcp.calendar_connector import CalendarSafetyError
        mock_client = MagicMock()
        mock_client.create_event.side_effect = CalendarSafetyError("blocked")
        mock_get_client.return_value = mock_client

        from apple_calendar_mcp.server_fastmcp import create_event
        result = create_event(
            calendar_name="Personal",
            summary="Test",
            start_date="2026-03-15T14:00:00",
            end_date="2026-03-15T15:00:00",
        )
        assert "Error" in result
        assert isinstance(result, str)


class TestGetEventsTool:
    """Tests for the get_events MCP tool."""

    @patch("apple_calendar_mcp.server_fastmcp.get_client")
    def test_returns_formatted_event_list(self, mock_get_client):
        mock_client = MagicMock()
        mock_client.get_events.return_value = [
            {"uid": "ABC-123", "summary": "Team Meeting", "start_date": "2026-03-15T14:00:00Z",
             "end_date": "2026-03-15T15:00:00Z", "allday_event": False, "location": "Room 4",
             "description": "Weekly sync", "url": "", "status": "confirmed", "calendar_name": "Work"},
        ]
        mock_get_client.return_value = mock_client

        from apple_calendar_mcp.server_fastmcp import get_events
        result = get_events(calendar_name="Work", start_date="2026-03-15T00:00:00", end_date="2026-03-16T00:00:00")
        assert "Team Meeting" in result
        assert "Room 4" in result
        assert isinstance(result, str)

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


class TestUpdateEventTool:
    """Tests for the update_event MCP tool."""

    @patch("apple_calendar_mcp.server_fastmcp.get_client")
    def test_returns_success_message(self, mock_get_client):
        mock_client = MagicMock()
        mock_client.update_event.return_value = {"uid": "ABC-123", "updated_fields": ["summary"]}
        mock_get_client.return_value = mock_client

        from apple_calendar_mcp.server_fastmcp import update_event
        result = update_event(calendar_name="Work", event_uid="ABC-123", summary="New Title")
        assert "ABC-123" in result
        assert "summary" in result
        assert isinstance(result, str)

    @patch("apple_calendar_mcp.server_fastmcp.get_client")
    def test_returns_error_on_failure(self, mock_get_client):
        mock_client = MagicMock()
        mock_client.update_event.side_effect = Exception("Event not found")
        mock_get_client.return_value = mock_client

        from apple_calendar_mcp.server_fastmcp import update_event
        result = update_event(calendar_name="Work", event_uid="BAD-UID", summary="X")
        assert "Error" in result
        assert isinstance(result, str)

    @patch("apple_calendar_mcp.server_fastmcp.get_client")
    def test_passes_none_for_omitted_fields(self, mock_get_client):
        mock_client = MagicMock()
        mock_client.update_event.return_value = {"uid": "ABC-123", "updated_fields": ["summary"]}
        mock_get_client.return_value = mock_client

        from apple_calendar_mcp.server_fastmcp import update_event
        update_event(calendar_name="Work", event_uid="ABC-123", summary="New")
        call_kwargs = mock_client.update_event.call_args[1]
        assert call_kwargs["location"] is None
        assert call_kwargs["description"] is None
        assert call_kwargs["url"] is None
        assert call_kwargs["allday_event"] is None

    @patch("apple_calendar_mcp.server_fastmcp.get_client")
    def test_passes_empty_string_through(self, mock_get_client):
        mock_client = MagicMock()
        mock_client.update_event.return_value = {"uid": "ABC-123", "updated_fields": ["location"]}
        mock_get_client.return_value = mock_client

        from apple_calendar_mcp.server_fastmcp import update_event
        update_event(calendar_name="Work", event_uid="ABC-123", location="")
        call_kwargs = mock_client.update_event.call_args[1]
        assert call_kwargs["location"] == ""


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
        )


class TestServerConfiguration:
    """Tests for MCP server configuration."""

    def test_server_has_instructions(self):
        # The mcp server should have instructions set
        assert mcp.instructions is not None
        assert len(mcp.instructions) > 0

    def test_server_name(self):
        assert mcp.name == "apple-calendar-mcp"
