"""Unit tests for CalendarConnector — core helpers and get_calendars."""
import json
import subprocess
from pathlib import Path
from unittest.mock import patch, MagicMock

import pytest

from apple_calendar_mcp.calendar_connector import (
    run_applescript,
    run_swift_helper,
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


# ── run_swift_helper ─────────────────────────────────────────────────────────


class TestRunSwiftHelper:
    """Tests for the run_swift_helper function."""

    @patch("apple_calendar_mcp.calendar_connector.subprocess.run")
    def test_returns_stdout_stripped(self, mock_run):
        mock_run.return_value = MagicMock(stdout='  [{"uid": "123"}]  \n')
        result = run_swift_helper("get_events", ["--calendar", "Work"])
        assert result == '[{"uid": "123"}]'

    @patch("apple_calendar_mcp.calendar_connector.subprocess.run")
    def test_calls_swift_with_script_path_and_args(self, mock_run):
        mock_run.return_value = MagicMock(stdout="[]")
        run_swift_helper("get_events", ["--calendar", "Work", "--start", "2026-03-15"])
        call_args = mock_run.call_args
        cmd = call_args[0][0]
        assert cmd[0] == "swift"
        assert cmd[1].endswith("get_events.swift")
        assert "--calendar" in cmd
        assert "Work" in cmd

    @patch("apple_calendar_mcp.calendar_connector.subprocess.run")
    def test_script_path_relative_to_package(self, mock_run):
        mock_run.return_value = MagicMock(stdout="[]")
        run_swift_helper("get_events", [])
        cmd = mock_run.call_args[0][0]
        script_path = Path(cmd[1])
        assert script_path.parent.name == "swift"
        assert script_path.parent.parent.name == "apple_calendar_mcp"

    @patch("apple_calendar_mcp.calendar_connector.subprocess.run")
    def test_custom_timeout(self, mock_run):
        mock_run.return_value = MagicMock(stdout="[]")
        run_swift_helper("get_events", [], timeout=120)
        assert mock_run.call_args[1]["timeout"] == 120

    @patch("apple_calendar_mcp.calendar_connector.subprocess.run")
    def test_called_process_error_propagates(self, mock_run):
        mock_run.side_effect = subprocess.CalledProcessError(
            returncode=1, cmd="swift", stderr="compilation error"
        )
        with pytest.raises(subprocess.CalledProcessError):
            run_swift_helper("get_events", [])

    @patch("apple_calendar_mcp.calendar_connector.subprocess.run")
    def test_timeout_expired_propagates(self, mock_run):
        mock_run.side_effect = subprocess.TimeoutExpired(cmd="swift", timeout=30)
        with pytest.raises(subprocess.TimeoutExpired):
            run_swift_helper("get_events", [])


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

    @patch("apple_calendar_mcp.calendar_connector.run_swift_helper")
    def test_returns_list_of_calendar_dicts(self, mock_swift):
        mock_swift.return_value = json.dumps([
            {"name": "Personal", "writable": True, "description": "", "color": "#0072FF"},
            {"name": "Work", "writable": True, "description": "", "color": "#FF0023"},
        ])
        result = self.connector.get_calendars()
        assert isinstance(result, list)
        assert len(result) == 2
        assert result[0]["name"] == "Personal"
        assert result[1]["name"] == "Work"

    @patch("apple_calendar_mcp.calendar_connector.run_swift_helper")
    def test_calendar_has_expected_keys(self, mock_swift):
        mock_swift.return_value = json.dumps([
            {"name": "Personal", "writable": True, "description": "my cal", "color": "#0072FF"},
        ])
        result = self.connector.get_calendars()
        cal = result[0]
        assert "name" in cal
        assert "writable" in cal
        assert "description" in cal
        assert "color" in cal

    @patch("apple_calendar_mcp.calendar_connector.run_swift_helper")
    def test_empty_calendar_list(self, mock_swift):
        mock_swift.return_value = json.dumps([])
        result = self.connector.get_calendars()
        assert result == []

    @patch("apple_calendar_mcp.calendar_connector.run_swift_helper")
    def test_read_only_calendar(self, mock_swift):
        mock_swift.return_value = json.dumps([
            {"name": "Holidays", "writable": False, "description": "US Holidays", "color": "#8882FE"},
        ])
        result = self.connector.get_calendars()
        assert result[0]["writable"] is False

    @patch("apple_calendar_mcp.calendar_connector.run_swift_helper")
    def test_calendar_with_empty_description(self, mock_swift):
        mock_swift.return_value = json.dumps([
            {"name": "Work", "writable": True, "description": "", "color": "#FF0000"},
        ])
        result = self.connector.get_calendars()
        assert result[0]["description"] == ""

    @patch("apple_calendar_mcp.calendar_connector.run_swift_helper")
    def test_calls_swift_helper(self, mock_swift):
        """Verify get_calendars uses the Swift helper."""
        mock_swift.return_value = json.dumps([])
        self.connector.get_calendars()
        mock_swift.assert_called_once_with("get_calendars", [])

    @patch("apple_calendar_mcp.calendar_connector.run_swift_helper")
    def test_handles_access_denied(self, mock_swift):
        mock_swift.return_value = json.dumps(
            {"error": "calendar_access_denied", "message": "Access denied"}
        )
        with pytest.raises(PermissionError, match="Access denied"):
            self.connector.get_calendars()


# ── create_calendar ─────────────────────────────────────────────────────────


class TestCreateCalendar:
    """Tests for CalendarConnector.create_calendar()."""

    def setup_method(self):
        self.connector = CalendarConnector(enable_safety_checks=False)

    @patch("apple_calendar_mcp.calendar_connector.run_applescript")
    def test_creates_calendar(self, mock_run):
        mock_run.return_value = "calendar id ABC-123"
        result = self.connector.create_calendar("New Calendar")
        assert result == {"name": "New Calendar"}
        script = mock_run.call_args[0][0]
        assert 'make new calendar' in script
        assert 'name:"New Calendar"' in script

    @patch("apple_calendar_mcp.calendar_connector.run_applescript")
    def test_escapes_special_characters(self, mock_run):
        mock_run.return_value = "calendar id ABC-123"
        self.connector.create_calendar('Cal with "quotes"')
        script = mock_run.call_args[0][0]
        assert 'Cal with \\"quotes\\"' in script


# ── delete_calendar ─────────────────────────────────────────────────────────


class TestDeleteCalendar:
    """Tests for CalendarConnector.delete_calendar()."""

    def setup_method(self):
        self.connector = CalendarConnector(enable_safety_checks=False)

    @patch("apple_calendar_mcp.calendar_connector.run_applescript")
    def test_deletes_calendar(self, mock_run):
        mock_run.return_value = ""
        result = self.connector.delete_calendar("Old Calendar")
        assert result == {"name": "Old Calendar"}
        script = mock_run.call_args[0][0]
        assert 'delete calendar "Old Calendar"' in script

    @patch("apple_calendar_mcp.calendar_connector.run_applescript")
    def test_not_found_raises_error(self, mock_run):
        mock_run.side_effect = subprocess.CalledProcessError(
            returncode=1, cmd="osascript", stderr="Calendar not found"
        )
        with pytest.raises(ValueError, match="not found"):
            self.connector.delete_calendar("Nonexistent")

    def test_safety_blocks_non_test_calendar(self):
        connector = CalendarConnector(enable_safety_checks=True)
        with pytest.raises(CalendarSafetyError, match="not an allowed test calendar"):
            connector.delete_calendar("Personal")


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
        assert "recurrence" not in script

    @patch("apple_calendar_mcp.calendar_connector.run_applescript")
    def test_creates_recurring_event(self, mock_run):
        mock_run.return_value = "REC-UID"
        self.connector.create_event(
            calendar_name="MCP-Test-Calendar",
            summary="Weekly Standup",
            start_date="2026-07-01T09:00:00",
            end_date="2026-07-01T09:30:00",
            recurrence_rule="FREQ=WEEKLY;BYDAY=MO,WE,FR",
        )
        script = mock_run.call_args[0][0]
        assert 'recurrence:"FREQ=WEEKLY;BYDAY=MO,WE,FR"' in script


# ── get_events ──────────────────────────────────────────────────────────────


class TestGetEvents:
    """Tests for CalendarConnector.get_events()."""

    def setup_method(self):
        self.connector = CalendarConnector()

    @patch("apple_calendar_mcp.calendar_connector.run_swift_helper")
    def test_calls_swift_helper_with_correct_args(self, mock_swift):
        mock_swift.return_value = "[]"
        self.connector.get_events(
            calendar_name="Work",
            start_date="2026-03-15T00:00:00",
            end_date="2026-03-16T00:00:00",
        )
        mock_swift.assert_called_once_with(
            "get_events",
            ["--calendar", "Work", "--start", "2026-03-15T00:00:00", "--end", "2026-03-16T00:00:00"],
        )

    @patch("apple_calendar_mcp.calendar_connector.run_swift_helper")
    def test_parses_json_response(self, mock_swift):
        mock_swift.return_value = json.dumps([
            {"uid": "ABC-123", "summary": "Meeting", "start_date": "2026-03-15T14:00:00",
             "end_date": "2026-03-15T15:00:00", "allday_event": False, "location": "",
             "description": "", "url": "", "status": "confirmed", "calendar_name": "Work"},
        ])
        result = self.connector.get_events("Work", "2026-03-15T00:00:00", "2026-03-16T00:00:00")
        assert isinstance(result, list)
        assert len(result) == 1
        assert result[0]["uid"] == "ABC-123"
        assert result[0]["summary"] == "Meeting"

    @patch("apple_calendar_mcp.calendar_connector.run_swift_helper")
    def test_returns_empty_list_when_no_events(self, mock_swift):
        mock_swift.return_value = "[]"
        result = self.connector.get_events("Work", "2026-03-15T00:00:00", "2026-03-16T00:00:00")
        assert result == []

    def test_invalid_start_date_raises_error(self):
        with pytest.raises(ValueError, match="Invalid date format"):
            self.connector.get_events("Work", "not-a-date", "2026-03-16T00:00:00")

    def test_invalid_end_date_raises_error(self):
        with pytest.raises(ValueError, match="Invalid date format"):
            self.connector.get_events("Work", "2026-03-15T00:00:00", "not-a-date")

    @patch("apple_calendar_mcp.calendar_connector.run_swift_helper")
    def test_handles_authorization_error(self, mock_swift):
        mock_swift.return_value = json.dumps(
            {"error": "calendar_access_denied", "message": "Access denied"}
        )
        with pytest.raises(PermissionError, match="Access denied"):
            self.connector.get_events("Work", "2026-03-15T00:00:00", "2026-03-16T00:00:00")

    @patch("apple_calendar_mcp.calendar_connector.run_swift_helper")
    def test_handles_calendar_not_found_error(self, mock_swift):
        mock_swift.return_value = json.dumps(
            {"error": "calendar_not_found", "message": "Calendar 'Foo' not found."}
        )
        with pytest.raises(ValueError, match="Calendar 'Foo' not found"):
            self.connector.get_events("Foo", "2026-03-15T00:00:00", "2026-03-16T00:00:00")

    @patch("apple_calendar_mcp.calendar_connector.run_swift_helper")
    def test_date_only_format_accepted(self, mock_swift):
        mock_swift.return_value = "[]"
        self.connector.get_events("Work", "2026-03-15", "2026-03-16")
        mock_swift.assert_called_once()

    @patch("apple_calendar_mcp.calendar_connector.run_swift_helper")
    def test_recurring_event_fields_returned(self, mock_swift):
        mock_swift.return_value = json.dumps([
            {"uid": "REC-123", "summary": "Weekly Standup", "start_date": "2026-07-01T09:00:00",
             "end_date": "2026-07-01T09:30:00", "allday_event": False, "location": "",
             "description": "", "url": "", "status": "confirmed", "calendar_name": "Work",
             "is_recurring": True, "recurrence_rule": "FREQ=WEEKLY;INTERVAL=1;BYDAY=MO,WE,FR",
             "is_detached": False, "occurrence_date": "2026-07-01T09:00:00"},
        ])
        result = self.connector.get_events("Work", "2026-07-01", "2026-07-02")
        event = result[0]
        assert event["is_recurring"] is True
        assert "FREQ=WEEKLY" in event["recurrence_rule"]
        assert event["is_detached"] is False
        assert event["occurrence_date"] == "2026-07-01T09:00:00"


# ── get_availability ────────────────────────────────────────────────────────


class TestGetAvailability:
    """Tests for CalendarConnector.get_availability()."""

    def setup_method(self):
        self.connector = CalendarConnector()

    def _make_event(self, start, end, allday=False, calendar="Work"):
        return {
            "uid": "UID-1", "summary": "Event", "start_date": start,
            "end_date": end, "allday_event": allday, "location": "",
            "description": "", "url": "", "status": "confirmed",
            "calendar_name": calendar,
        }

    @patch("apple_calendar_mcp.calendar_connector.run_swift_helper")
    def test_no_events_entire_range_free(self, mock_swift):
        mock_swift.return_value = "[]"
        result = self.connector.get_availability(
            ["Work"], "2026-03-15T09:00:00", "2026-03-15T17:00:00"
        )
        assert len(result) == 1
        assert result[0]["start_date"] == "2026-03-15T09:00:00"
        assert result[0]["end_date"] == "2026-03-15T17:00:00"
        assert result[0]["duration_minutes"] == 480

    @patch("apple_calendar_mcp.calendar_connector.run_swift_helper")
    def test_single_event_gaps_before_and_after(self, mock_swift):
        mock_swift.return_value = json.dumps([
            self._make_event("2026-03-15T10:00:00", "2026-03-15T11:00:00"),
        ])
        result = self.connector.get_availability(
            ["Work"], "2026-03-15T09:00:00", "2026-03-15T17:00:00"
        )
        assert len(result) == 2
        assert result[0]["start_date"] == "2026-03-15T09:00:00"
        assert result[0]["end_date"] == "2026-03-15T10:00:00"
        assert result[0]["duration_minutes"] == 60
        assert result[1]["start_date"] == "2026-03-15T11:00:00"
        assert result[1]["end_date"] == "2026-03-15T17:00:00"
        assert result[1]["duration_minutes"] == 360

    @patch("apple_calendar_mcp.calendar_connector.run_swift_helper")
    def test_multiple_events_gaps_between(self, mock_swift):
        mock_swift.return_value = json.dumps([
            self._make_event("2026-03-15T09:00:00", "2026-03-15T10:00:00"),
            self._make_event("2026-03-15T11:00:00", "2026-03-15T12:00:00"),
        ])
        result = self.connector.get_availability(
            ["Work"], "2026-03-15T09:00:00", "2026-03-15T13:00:00"
        )
        assert len(result) == 2
        assert result[0]["start_date"] == "2026-03-15T10:00:00"
        assert result[0]["end_date"] == "2026-03-15T11:00:00"
        assert result[1]["start_date"] == "2026-03-15T12:00:00"
        assert result[1]["end_date"] == "2026-03-15T13:00:00"

    @patch("apple_calendar_mcp.calendar_connector.run_swift_helper")
    def test_overlapping_events_merged(self, mock_swift):
        """Two overlapping events across calendars should merge into one busy block."""
        def swift_side_effect(script_name, args):
            cal = args[args.index("--calendar") + 1]
            if cal == "Work":
                return json.dumps([
                    self._make_event("2026-03-15T09:00:00", "2026-03-15T11:00:00", calendar="Work"),
                ])
            else:
                return json.dumps([
                    self._make_event("2026-03-15T10:00:00", "2026-03-15T12:00:00", calendar="Personal"),
                ])
        mock_swift.side_effect = swift_side_effect
        result = self.connector.get_availability(
            ["Work", "Personal"], "2026-03-15T08:00:00", "2026-03-15T14:00:00"
        )
        assert len(result) == 2
        assert result[0]["start_date"] == "2026-03-15T08:00:00"
        assert result[0]["end_date"] == "2026-03-15T09:00:00"
        assert result[1]["start_date"] == "2026-03-15T12:00:00"
        assert result[1]["end_date"] == "2026-03-15T14:00:00"

    @patch("apple_calendar_mcp.calendar_connector.run_swift_helper")
    def test_adjacent_events_no_gap(self, mock_swift):
        mock_swift.return_value = json.dumps([
            self._make_event("2026-03-15T09:00:00", "2026-03-15T10:00:00"),
            self._make_event("2026-03-15T10:00:00", "2026-03-15T11:00:00"),
        ])
        result = self.connector.get_availability(
            ["Work"], "2026-03-15T09:00:00", "2026-03-15T11:00:00"
        )
        assert len(result) == 0

    @patch("apple_calendar_mcp.calendar_connector.run_swift_helper")
    def test_allday_event_blocks_full_day(self, mock_swift):
        mock_swift.return_value = json.dumps([
            self._make_event("2026-03-15", "2026-03-16", allday=True),
        ])
        result = self.connector.get_availability(
            ["Work"], "2026-03-15T00:00:00", "2026-03-16T00:00:00"
        )
        assert len(result) == 0

    @patch("apple_calendar_mcp.calendar_connector.run_swift_helper")
    def test_events_covering_entire_range(self, mock_swift):
        mock_swift.return_value = json.dumps([
            self._make_event("2026-03-15T08:00:00", "2026-03-15T18:00:00"),
        ])
        result = self.connector.get_availability(
            ["Work"], "2026-03-15T09:00:00", "2026-03-15T17:00:00"
        )
        assert len(result) == 0

    def test_invalid_start_date_raises(self):
        with pytest.raises(ValueError, match="Invalid date format"):
            self.connector.get_availability(["Work"], "not-a-date", "2026-03-16T00:00:00")

    def test_invalid_end_date_raises(self):
        with pytest.raises(ValueError, match="Invalid date format"):
            self.connector.get_availability(["Work"], "2026-03-15T00:00:00", "not-a-date")

    def test_empty_calendar_list_raises(self):
        with pytest.raises(ValueError, match="At least one calendar"):
            self.connector.get_availability([], "2026-03-15T00:00:00", "2026-03-16T00:00:00")

    @patch("apple_calendar_mcp.calendar_connector.run_swift_helper")
    def test_multiple_calendars_combined(self, mock_swift):
        """Events from multiple calendars should be merged for availability."""
        def swift_side_effect(script_name, args):
            cal = args[args.index("--calendar") + 1]
            if cal == "Work":
                return json.dumps([
                    self._make_event("2026-03-15T09:00:00", "2026-03-15T10:00:00", calendar="Work"),
                ])
            else:
                return json.dumps([
                    self._make_event("2026-03-15T14:00:00", "2026-03-15T15:00:00", calendar="Personal"),
                ])
        mock_swift.side_effect = swift_side_effect
        result = self.connector.get_availability(
            ["Work", "Personal"], "2026-03-15T08:00:00", "2026-03-15T16:00:00"
        )
        assert len(result) == 3
        assert result[0]["end_date"] == "2026-03-15T09:00:00"
        assert result[1]["start_date"] == "2026-03-15T10:00:00"
        assert result[1]["end_date"] == "2026-03-15T14:00:00"
        assert result[2]["start_date"] == "2026-03-15T15:00:00"


# ── update_event ────────────────────────────────────────────────────────────


class TestUpdateEvent:
    """Tests for CalendarConnector.update_event()."""

    def setup_method(self):
        self.connector = CalendarConnector(enable_safety_checks=False)

    @patch("apple_calendar_mcp.calendar_connector.run_applescript")
    def test_updates_summary(self, mock_run):
        mock_run.return_value = "ABC-123"
        self.connector.update_event("MCP-Test-Calendar", "ABC-123", summary="New Title")
        script = mock_run.call_args[0][0]
        assert 'set summary of evt to "New Title"' in script

    @patch("apple_calendar_mcp.calendar_connector.run_applescript")
    def test_updates_start_date(self, mock_run):
        mock_run.return_value = "ABC-123"
        self.connector.update_event("MCP-Test-Calendar", "ABC-123", start_date="2026-03-15T14:30:00")
        script = mock_run.call_args[0][0]
        assert 'set start date of evt to date "March 15, 2026 02:30:00 PM"' in script

    @patch("apple_calendar_mcp.calendar_connector.run_applescript")
    def test_updates_end_date(self, mock_run):
        mock_run.return_value = "ABC-123"
        self.connector.update_event("MCP-Test-Calendar", "ABC-123", end_date="2026-03-15T15:30:00")
        script = mock_run.call_args[0][0]
        assert 'set end date of evt to date "March 15, 2026 03:30:00 PM"' in script

    @patch("apple_calendar_mcp.calendar_connector.run_applescript")
    def test_updates_location(self, mock_run):
        mock_run.return_value = "ABC-123"
        self.connector.update_event("MCP-Test-Calendar", "ABC-123", location="Room B")
        script = mock_run.call_args[0][0]
        assert 'set location of evt to "Room B"' in script

    @patch("apple_calendar_mcp.calendar_connector.run_applescript")
    def test_updates_description(self, mock_run):
        mock_run.return_value = "ABC-123"
        self.connector.update_event("MCP-Test-Calendar", "ABC-123", description="New notes")
        script = mock_run.call_args[0][0]
        assert 'set description of evt to "New notes"' in script

    @patch("apple_calendar_mcp.calendar_connector.run_applescript")
    def test_updates_url(self, mock_run):
        mock_run.return_value = "ABC-123"
        self.connector.update_event("MCP-Test-Calendar", "ABC-123", url="https://example.com")
        script = mock_run.call_args[0][0]
        assert 'set url of evt to "https://example.com"' in script

    @patch("apple_calendar_mcp.calendar_connector.run_applescript")
    def test_updates_allday_true(self, mock_run):
        mock_run.return_value = "ABC-123"
        self.connector.update_event("MCP-Test-Calendar", "ABC-123", allday_event=True)
        script = mock_run.call_args[0][0]
        assert "set allday event of evt to true" in script

    @patch("apple_calendar_mcp.calendar_connector.run_applescript")
    def test_updates_allday_false(self, mock_run):
        mock_run.return_value = "ABC-123"
        self.connector.update_event("MCP-Test-Calendar", "ABC-123", allday_event=False)
        script = mock_run.call_args[0][0]
        assert "set allday event of evt to false" in script

    @patch("apple_calendar_mcp.calendar_connector.run_applescript")
    def test_updates_multiple_fields(self, mock_run):
        mock_run.return_value = "ABC-123"
        self.connector.update_event("MCP-Test-Calendar", "ABC-123", summary="New", location="Room C")
        script = mock_run.call_args[0][0]
        assert 'set summary of evt to "New"' in script
        assert 'set location of evt to "Room C"' in script

    @patch("apple_calendar_mcp.calendar_connector.run_applescript")
    def test_only_provided_fields_set(self, mock_run):
        mock_run.return_value = "ABC-123"
        self.connector.update_event("MCP-Test-Calendar", "ABC-123", summary="New Title")
        script = mock_run.call_args[0][0]
        assert "set summary of evt" in script
        assert "set location of evt" not in script
        assert "set description of evt" not in script
        assert "set url of evt" not in script
        assert "set start date of evt" not in script
        assert "set end date of evt" not in script
        assert "set allday event of evt" not in script

    @patch("apple_calendar_mcp.calendar_connector.run_applescript")
    def test_escapes_special_characters(self, mock_run):
        mock_run.return_value = "ABC-123"
        self.connector.update_event("MCP-Test-Calendar", "ABC-123", summary='Say "hello"')
        script = mock_run.call_args[0][0]
        assert 'Say \\"hello\\"' in script

    def test_invalid_date_raises(self):
        with pytest.raises(ValueError, match="Invalid date format"):
            self.connector.update_event("MCP-Test-Calendar", "ABC-123", start_date="not-a-date")

    def test_safety_blocks_non_test_calendar(self):
        connector = CalendarConnector(enable_safety_checks=True)
        with pytest.raises(CalendarSafetyError, match="not an allowed test calendar"):
            connector.update_event("Personal", "ABC-123", summary="Test")

    def test_no_fields_raises(self):
        with pytest.raises(ValueError, match="At least one field"):
            self.connector.update_event("MCP-Test-Calendar", "ABC-123")

    @patch("apple_calendar_mcp.calendar_connector.run_applescript")
    def test_returns_dict_with_uid_and_updated_fields(self, mock_run):
        mock_run.return_value = "ABC-123"
        result = self.connector.update_event("MCP-Test-Calendar", "ABC-123", summary="New", location="Room")
        assert result == {"uid": "ABC-123", "updated_fields": ["summary", "location"]}

    @patch("apple_calendar_mcp.calendar_connector.run_applescript")
    def test_uses_whose_uid_clause(self, mock_run):
        mock_run.return_value = "ABC-123"
        self.connector.update_event("MCP-Test-Calendar", "ABC-123", summary="X")
        script = mock_run.call_args[0][0]
        assert 'whose uid is "ABC-123"' in script

    @patch("apple_calendar_mcp.calendar_connector.run_applescript")
    def test_clear_field_with_empty_string(self, mock_run):
        mock_run.return_value = "ABC-123"
        self.connector.update_event("MCP-Test-Calendar", "ABC-123", location="")
        script = mock_run.call_args[0][0]
        assert 'set location of evt to ""' in script


# ── delete_events ──────────────────────────────────────────────────────────


class TestDeleteEvents:
    """Tests for CalendarConnector.delete_events()."""

    def setup_method(self):
        self.connector = CalendarConnector(enable_safety_checks=False)

    @patch("apple_calendar_mcp.calendar_connector.run_applescript")
    def test_deletes_single_event(self, mock_run):
        mock_run.return_value = ""
        result = self.connector.delete_events("MCP-Test-Calendar", "ABC-123")
        assert result["deleted_uids"] == ["ABC-123"]
        assert result["not_found_uids"] == []
        script = mock_run.call_args[0][0]
        assert 'whose uid is "ABC-123"' in script
        assert "delete evt" in script

    @patch("apple_calendar_mcp.calendar_connector.run_applescript")
    def test_deletes_multiple_events(self, mock_run):
        mock_run.return_value = ""
        result = self.connector.delete_events("MCP-Test-Calendar", ["UID-1", "UID-2", "UID-3"])
        assert result["deleted_uids"] == ["UID-1", "UID-2", "UID-3"]
        assert result["not_found_uids"] == []
        assert mock_run.call_count == 3

    @patch("apple_calendar_mcp.calendar_connector.run_applescript")
    def test_normalizes_single_uid_to_list(self, mock_run):
        mock_run.return_value = ""
        result = self.connector.delete_events("MCP-Test-Calendar", "SINGLE-UID")
        assert isinstance(result["deleted_uids"], list)
        assert result["deleted_uids"] == ["SINGLE-UID"]

    @patch("apple_calendar_mcp.calendar_connector.run_applescript")
    def test_escapes_uid_in_script(self, mock_run):
        mock_run.return_value = ""
        self.connector.delete_events("MCP-Test-Calendar", 'UID-with-"quotes"')
        script = mock_run.call_args[0][0]
        assert 'UID-with-\\"quotes\\"' in script

    def test_safety_blocks_non_test_calendar(self):
        connector = CalendarConnector(enable_safety_checks=True)
        with pytest.raises(CalendarSafetyError, match="not an allowed test calendar"):
            connector.delete_events("Personal", "ABC-123")

    def test_empty_list_raises(self):
        with pytest.raises(ValueError, match="At least one event UID"):
            self.connector.delete_events("MCP-Test-Calendar", [])

    @patch("apple_calendar_mcp.calendar_connector.run_applescript")
    def test_not_found_uid(self, mock_run):
        mock_run.side_effect = subprocess.CalledProcessError(
            returncode=1, cmd="osascript", stderr="Event not found"
        )
        result = self.connector.delete_events("MCP-Test-Calendar", "BAD-UID")
        assert result["deleted_uids"] == []
        assert result["not_found_uids"] == ["BAD-UID"]

    @patch("apple_calendar_mcp.calendar_connector.run_applescript")
    def test_batch_partial_failure(self, mock_run):
        def side_effect(script):
            if "UID-2" in script:
                raise subprocess.CalledProcessError(
                    returncode=1, cmd="osascript", stderr="Event not found"
                )
            return ""
        mock_run.side_effect = side_effect
        result = self.connector.delete_events("MCP-Test-Calendar", ["UID-1", "UID-2", "UID-3"])
        assert result["deleted_uids"] == ["UID-1", "UID-3"]
        assert result["not_found_uids"] == ["UID-2"]

    @patch("apple_calendar_mcp.calendar_connector.run_applescript")
    def test_uses_delete_keyword(self, mock_run):
        mock_run.return_value = ""
        self.connector.delete_events("MCP-Test-Calendar", "ABC-123")
        script = mock_run.call_args[0][0]
        assert "delete evt" in script
