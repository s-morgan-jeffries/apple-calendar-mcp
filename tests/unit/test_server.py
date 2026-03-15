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


class TestServerConfiguration:
    """Tests for MCP server configuration."""

    def test_server_has_instructions(self):
        # The mcp server should have instructions set
        assert mcp.instructions is not None
        assert len(mcp.instructions) > 0

    def test_server_name(self):
        assert mcp.name == "apple-calendar-mcp"
