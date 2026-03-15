"""Unit tests for CalendarConnector — core helpers and get_calendars."""
import json
import subprocess
from unittest.mock import patch, MagicMock

import pytest

from apple_calendar_mcp.calendar_connector import (
    run_applescript,
    CalendarConnector,
    CalendarSafetyError,
)


# ── run_applescript ──────────────────────────────────────────────────────────


class TestRunApplescript:
    """Tests for the run_applescript helper function."""

    @patch("apple_calendar_mcp.calendar_connector.subprocess.run")
    def test_returns_stdout_stripped(self, mock_run):
        mock_run.return_value = MagicMock(stdout="  hello world  \n")
        result = run_applescript("some script")
        assert result == "hello world"

    @patch("apple_calendar_mcp.calendar_connector.subprocess.run")
    def test_calls_osascript_with_script(self, mock_run):
        mock_run.return_value = MagicMock(stdout="")
        run_applescript("tell application \"Calendar\" to name of every calendar")
        mock_run.assert_called_once_with(
            ["osascript", "-e", "tell application \"Calendar\" to name of every calendar"],
            capture_output=True,
            text=True,
            check=True,
            timeout=60,
        )

    @patch("apple_calendar_mcp.calendar_connector.subprocess.run")
    def test_custom_timeout(self, mock_run):
        mock_run.return_value = MagicMock(stdout="")
        run_applescript("script", timeout=120)
        mock_run.assert_called_once_with(
            ["osascript", "-e", "script"],
            capture_output=True,
            text=True,
            check=True,
            timeout=120,
        )

    def test_timeout_exceeds_max_raises_error(self):
        with pytest.raises(ValueError, match="Timeout cannot exceed 300 seconds"):
            run_applescript("script", timeout=301)

    @patch("apple_calendar_mcp.calendar_connector.subprocess.run")
    def test_timeout_expired_propagates(self, mock_run):
        mock_run.side_effect = subprocess.TimeoutExpired(cmd="osascript", timeout=60)
        with pytest.raises(subprocess.TimeoutExpired):
            run_applescript("script")

    @patch("apple_calendar_mcp.calendar_connector.subprocess.run")
    def test_called_process_error_propagates(self, mock_run):
        mock_run.side_effect = subprocess.CalledProcessError(
            returncode=1, cmd="osascript", stderr="error"
        )
        with pytest.raises(subprocess.CalledProcessError):
            run_applescript("script")


# ── _escape_applescript_string ───────────────────────────────────────────────


class TestEscapeApplescriptString:
    """Tests for string escaping before embedding in AppleScript."""

    def setup_method(self):
        self.connector = CalendarConnector()

    def test_escapes_double_quotes(self):
        assert self.connector._escape_applescript_string('say "hello"') == 'say \\"hello\\"'

    def test_escapes_backslashes(self):
        assert self.connector._escape_applescript_string("path\\to\\file") == "path\\\\to\\\\file"

    def test_escapes_both(self):
        result = self.connector._escape_applescript_string('a\\b"c')
        assert result == 'a\\\\b\\"c'

    def test_empty_string(self):
        assert self.connector._escape_applescript_string("") == ""

    def test_none_returns_empty(self):
        assert self.connector._escape_applescript_string(None) == ""

    def test_no_special_chars(self):
        assert self.connector._escape_applescript_string("plain text") == "plain text"


# ── _iso_to_applescript_date ─────────────────────────────────────────────────


class TestIsoToApplescriptDate:
    """Tests for ISO 8601 to AppleScript date conversion."""

    def setup_method(self):
        self.connector = CalendarConnector()

    def test_date_only(self):
        result = self.connector._iso_to_applescript_date("2026-03-15")
        assert result == "March 15, 2026 12:00:00 AM"

    def test_date_with_time(self):
        result = self.connector._iso_to_applescript_date("2026-03-15T14:30:00")
        assert result == "March 15, 2026 02:30:00 PM"

    def test_date_with_midnight(self):
        result = self.connector._iso_to_applescript_date("2026-03-15T00:00:00")
        assert result == "March 15, 2026 12:00:00 AM"

    def test_date_with_noon(self):
        result = self.connector._iso_to_applescript_date("2026-03-15T12:00:00")
        assert result == "March 15, 2026 12:00:00 PM"

    def test_invalid_date_raises_error(self):
        with pytest.raises(ValueError, match="Invalid date format"):
            self.connector._iso_to_applescript_date("not-a-date")

    def test_date_with_z_suffix(self):
        result = self.connector._iso_to_applescript_date("2026-03-15T14:30:00Z")
        assert result == "March 15, 2026 02:30:00 PM"


# ── CalendarSafetyError ─────────────────────────────────────────────────────


class TestCalendarSafety:
    """Tests for calendar safety guards."""

    def test_safety_checks_enabled_by_default(self):
        connector = CalendarConnector()
        assert connector.enable_safety_checks is True

    def test_safety_checks_can_be_disabled(self):
        connector = CalendarConnector(enable_safety_checks=False)
        assert connector.enable_safety_checks is False


# ── _verify_calendar_safety ───────────────────────────────────────────────────


class TestVerifyCalendarSafety:
    """Tests for calendar safety verification on write operations."""

    def test_blocks_non_test_calendar_when_safety_enabled(self):
        connector = CalendarConnector(enable_safety_checks=True)
        with pytest.raises(CalendarSafetyError, match="not an allowed test calendar"):
            connector._verify_calendar_safety("Personal")

    def test_allows_test_calendar_when_safety_enabled(self):
        connector = CalendarConnector(enable_safety_checks=True)
        connector._verify_calendar_safety("MCP-Test-Calendar")  # should not raise

    def test_allows_second_test_calendar(self):
        connector = CalendarConnector(enable_safety_checks=True)
        connector._verify_calendar_safety("MCP-Test-Calendar-2")  # should not raise

    def test_allows_any_calendar_when_safety_disabled(self):
        connector = CalendarConnector(enable_safety_checks=False)
        connector._verify_calendar_safety("Personal")  # should not raise

    def test_blocks_empty_calendar_name_when_safety_enabled(self):
        connector = CalendarConnector(enable_safety_checks=True)
        with pytest.raises(CalendarSafetyError):
            connector._verify_calendar_safety("")


# ── get_calendars ────────────────────────────────────────────────────────────


class TestGetCalendars:
    """Tests for CalendarConnector.get_calendars()."""

    def setup_method(self):
        self.connector = CalendarConnector()

    @patch("apple_calendar_mcp.calendar_connector.run_applescript")
    def test_returns_list_of_calendar_dicts(self, mock_run):
        mock_run.return_value = json.dumps([
            {"name": "Personal", "writable": True, "description": "", "color": "#0072FF"},
            {"name": "Work", "writable": True, "description": "", "color": "#FF0023"},
        ])
        result = self.connector.get_calendars()
        assert isinstance(result, list)
        assert len(result) == 2
        assert result[0]["name"] == "Personal"
        assert result[1]["name"] == "Work"

    @patch("apple_calendar_mcp.calendar_connector.run_applescript")
    def test_calendar_has_expected_keys(self, mock_run):
        mock_run.return_value = json.dumps([
            {"name": "Personal", "writable": True, "description": "my cal", "color": "#0072FF"},
        ])
        result = self.connector.get_calendars()
        cal = result[0]
        assert "name" in cal
        assert "writable" in cal
        assert "description" in cal
        assert "color" in cal

    @patch("apple_calendar_mcp.calendar_connector.run_applescript")
    def test_empty_calendar_list(self, mock_run):
        mock_run.return_value = json.dumps([])
        result = self.connector.get_calendars()
        assert result == []

    @patch("apple_calendar_mcp.calendar_connector.run_applescript")
    def test_read_only_calendar(self, mock_run):
        mock_run.return_value = json.dumps([
            {"name": "Holidays", "writable": False, "description": "US Holidays", "color": "#8882FE"},
        ])
        result = self.connector.get_calendars()
        assert result[0]["writable"] is False

    @patch("apple_calendar_mcp.calendar_connector.run_applescript")
    def test_calendar_with_empty_description(self, mock_run):
        mock_run.return_value = json.dumps([
            {"name": "Work", "writable": True, "description": "", "color": "#FF0000"},
        ])
        result = self.connector.get_calendars()
        assert result[0]["description"] == ""

    @patch("apple_calendar_mcp.calendar_connector.run_applescript")
    def test_calls_applescript(self, mock_run):
        """Verify get_calendars executes an AppleScript command."""
        mock_run.return_value = json.dumps([])
        self.connector.get_calendars()
        mock_run.assert_called_once()
        script = mock_run.call_args[0][0]
        assert "Calendar" in script


# ── create_event ─────────────────────────────────────────────────────────────


class TestCreateEvent:
    """Tests for CalendarConnector.create_event()."""

    def setup_method(self):
        self.connector = CalendarConnector(enable_safety_checks=False)

    @patch("apple_calendar_mcp.calendar_connector.run_applescript")
    def test_creates_event_with_required_fields(self, mock_run):
        mock_run.return_value = "3290DD8F-17E9-4DCC-B5FA-764655253E7A"
        result = self.connector.create_event(
            calendar_name="MCP-Test-Calendar",
            summary="Team Meeting",
            start_date="2026-03-15T14:00:00",
            end_date="2026-03-15T15:00:00",
        )
        assert result == "3290DD8F-17E9-4DCC-B5FA-764655253E7A"
        script = mock_run.call_args[0][0]
        assert 'calendar "MCP-Test-Calendar"' in script
        assert "make new event" in script
        assert "Team Meeting" in script
        assert "March 15, 2026 02:00:00 PM" in script
        assert "March 15, 2026 03:00:00 PM" in script

    @patch("apple_calendar_mcp.calendar_connector.run_applescript")
    def test_creates_event_with_all_optional_fields(self, mock_run):
        mock_run.return_value = "ABCD-1234"
        self.connector.create_event(
            calendar_name="MCP-Test-Calendar",
            summary="Lunch",
            start_date="2026-03-15T12:00:00",
            end_date="2026-03-15T13:00:00",
            location="Conference Room A",
            description="Discuss project updates",
            url="https://example.com/meeting",
        )
        script = mock_run.call_args[0][0]
        assert "Conference Room A" in script
        assert "Discuss project updates" in script
        assert "https://example.com/meeting" in script

    @patch("apple_calendar_mcp.calendar_connector.run_applescript")
    def test_creates_allday_event(self, mock_run):
        mock_run.return_value = "ALLDAY-UID"
        self.connector.create_event(
            calendar_name="MCP-Test-Calendar",
            summary="Holiday",
            start_date="2026-03-15",
            end_date="2026-03-16",
            allday_event=True,
        )
        script = mock_run.call_args[0][0]
        assert "allday event:true" in script

    @patch("apple_calendar_mcp.calendar_connector.run_applescript")
    def test_escapes_special_characters(self, mock_run):
        mock_run.return_value = "ESC-UID"
        self.connector.create_event(
            calendar_name="MCP-Test-Calendar",
            summary='Meeting with "quotes"',
            start_date="2026-03-15T14:00:00",
            end_date="2026-03-15T15:00:00",
            location='Room "B"',
        )
        script = mock_run.call_args[0][0]
        assert '\\"quotes\\"' in script
        assert 'Room \\"B\\"' in script

    def test_invalid_start_date_raises_error(self):
        with pytest.raises(ValueError, match="Invalid date format"):
            self.connector.create_event(
                calendar_name="MCP-Test-Calendar",
                summary="Bad Date",
                start_date="not-a-date",
                end_date="2026-03-15T15:00:00",
            )

    def test_safety_check_blocks_non_test_calendar(self):
        connector = CalendarConnector(enable_safety_checks=True)
        with pytest.raises(CalendarSafetyError, match="not an allowed test calendar"):
            connector.create_event(
                calendar_name="Personal",
                summary="Test",
                start_date="2026-03-15T14:00:00",
                end_date="2026-03-15T15:00:00",
            )

    @patch("apple_calendar_mcp.calendar_connector.run_applescript")
    def test_applescript_failure_raises_exception(self, mock_run):
        mock_run.side_effect = subprocess.CalledProcessError(
            returncode=1, cmd="osascript", stderr="Calendar not found"
        )
        with pytest.raises(subprocess.CalledProcessError):
            self.connector.create_event(
                calendar_name="MCP-Test-Calendar",
                summary="Test",
                start_date="2026-03-15T14:00:00",
                end_date="2026-03-15T15:00:00",
            )

    @patch("apple_calendar_mcp.calendar_connector.run_applescript")
    def test_optional_fields_omitted_when_not_provided(self, mock_run):
        mock_run.return_value = "UID-123"
        self.connector.create_event(
            calendar_name="MCP-Test-Calendar",
            summary="Simple Event",
            start_date="2026-03-15T14:00:00",
            end_date="2026-03-15T15:00:00",
        )
        script = mock_run.call_args[0][0]
        assert "location" not in script.lower() or "set location" not in script
        assert "description" not in script.lower() or "set description" not in script
        assert "set url" not in script
