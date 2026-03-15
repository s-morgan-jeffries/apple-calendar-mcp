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


class TestServerConfiguration:
    """Tests for MCP server configuration."""

    def test_server_has_instructions(self):
        # The mcp server should have instructions set
        assert mcp.instructions is not None
        assert len(mcp.instructions) > 0

    def test_server_name(self):
        assert mcp.name == "apple-calendar-mcp"
