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
