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
            {"name": "Personal", "writable": True, "description": "", "color": "#0072FF", "source": "iCloud"},
            {"name": "Work", "writable": True, "description": "", "color": "#FF0023", "source": "Google"},
        ])
        result = self.connector.get_calendars()
        assert isinstance(result, list)
        assert len(result) == 2
        assert result[0]["name"] == "Personal"
        assert result[1]["name"] == "Work"

    @patch("apple_calendar_mcp.calendar_connector.run_swift_helper")
    def test_calendar_has_expected_keys(self, mock_swift):
        mock_swift.return_value = json.dumps([
            {"name": "Personal", "writable": True, "description": "my cal", "color": "#0072FF", "source": "iCloud"},
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
            {"name": "Holidays", "writable": False, "description": "US Holidays", "color": "#8882FE", "source": "Other"},
        ])
        result = self.connector.get_calendars()
        assert result[0]["writable"] is False

    @patch("apple_calendar_mcp.calendar_connector.run_swift_helper")
    def test_calendar_with_empty_description(self, mock_swift):
        mock_swift.return_value = json.dumps([
            {"name": "Work", "writable": True, "description": "", "color": "#FF0000", "source": "iCloud"},
        ])
        result = self.connector.get_calendars()
        assert result[0]["description"] == ""

    @patch("apple_calendar_mcp.calendar_connector.run_swift_helper")
    def test_calls_swift_helper(self, mock_swift):
        """Verify get_calendars uses the Swift helper."""
        mock_swift.return_value = json.dumps([])
        self.connector.get_calendars()
        mock_swift.assert_called_once_with("get_calendars", [], stdin_data=None)

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

    @patch("apple_calendar_mcp.calendar_connector.run_swift_helper")
    def test_creates_event_with_required_fields(self, mock_swift):
        mock_swift.return_value = json.dumps({"uid": "3290DD8F-17E9-4DCC-B5FA-764655253E7A"})
        result = self.connector.create_event(
            calendar_name="MCP-Test-Calendar",
            summary="Team Meeting",
            start_date="2026-03-15T14:00:00",
            end_date="2026-03-15T15:00:00",
        )
        assert result == "3290DD8F-17E9-4DCC-B5FA-764655253E7A"
        mock_swift.assert_called_once_with("create_event", [
            "--calendar", "MCP-Test-Calendar", "--summary", "Team Meeting",
            "--start", "2026-03-15T14:00:00", "--end", "2026-03-15T15:00:00",
        ], stdin_data=None)

    @patch("apple_calendar_mcp.calendar_connector.run_swift_helper")
    def test_creates_event_with_all_optional_fields(self, mock_swift):
        mock_swift.return_value = json.dumps({"uid": "ABCD-1234"})
        self.connector.create_event(
            calendar_name="MCP-Test-Calendar",
            summary="Lunch",
            start_date="2026-03-15T12:00:00",
            end_date="2026-03-15T13:00:00",
            location="Conference Room A",
            notes="Discuss project updates",
            url="https://example.com/meeting",
        )
        args = mock_swift.call_args[0][1]
        assert "--location" in args
        assert "Conference Room A" in args
        assert "--notes" in args
        assert "Discuss project updates" in args
        assert "--url" in args
        assert "https://example.com/meeting" in args

    @patch("apple_calendar_mcp.calendar_connector.run_swift_helper")
    def test_creates_allday_event(self, mock_swift):
        mock_swift.return_value = json.dumps({"uid": "ALLDAY-UID"})
        self.connector.create_event(
            calendar_name="MCP-Test-Calendar",
            summary="Holiday",
            start_date="2026-03-15",
            end_date="2026-03-16",
            allday_event=True,
        )
        args = mock_swift.call_args[0][1]
        assert "--allday" in args

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

    @patch("apple_calendar_mcp.calendar_connector.run_swift_helper")
    def test_calendar_not_found_raises_error(self, mock_swift):
        mock_swift.return_value = json.dumps(
            {"error": "calendar_not_found", "message": "Calendar 'Nope' not found."}
        )
        with pytest.raises(ValueError, match="not found"):
            self.connector.create_event(
                calendar_name="Nope",
                summary="Test",
                start_date="2026-03-15T14:00:00",
                end_date="2026-03-15T15:00:00",
            )

    @patch("apple_calendar_mcp.calendar_connector.run_swift_helper")
    def test_optional_fields_omitted_when_not_provided(self, mock_swift):
        mock_swift.return_value = json.dumps({"uid": "UID-123"})
        self.connector.create_event(
            calendar_name="MCP-Test-Calendar",
            summary="Simple Event",
            start_date="2026-03-15T14:00:00",
            end_date="2026-03-15T15:00:00",
        )
        args = mock_swift.call_args[0][1]
        assert "--location" not in args
        assert "--description" not in args
        assert "--url" not in args
        assert "--allday" not in args
        assert "--recurrence" not in args

    @patch("apple_calendar_mcp.calendar_connector.run_swift_helper")
    def test_creates_recurring_event(self, mock_swift):
        mock_swift.return_value = json.dumps({"uid": "REC-UID"})
        self.connector.create_event(
            calendar_name="MCP-Test-Calendar",
            summary="Weekly Standup",
            start_date="2026-07-01T09:00:00",
            end_date="2026-07-01T09:30:00",
            recurrence_rule="FREQ=WEEKLY;BYDAY=MO,WE,FR",
        )
        args = mock_swift.call_args[0][1]
        assert "--recurrence" in args
        assert "FREQ=WEEKLY;BYDAY=MO,WE,FR" in args


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
            stdin_data=None,
        )

    @patch("apple_calendar_mcp.calendar_connector.run_swift_helper")
    def test_parses_json_response(self, mock_swift):
        mock_swift.return_value = json.dumps([
            {"uid": "ABC-123", "summary": "Meeting", "start_date": "2026-03-15T14:00:00",
             "end_date": "2026-03-15T15:00:00", "allday_event": False, "location": "",
             "notes": "", "url": "", "status": "confirmed", "calendar_name": "Work"},
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
             "notes": "", "url": "", "status": "confirmed", "calendar_name": "Work",
             "is_recurring": True, "recurrence_rule": "FREQ=WEEKLY;INTERVAL=1;BYDAY=MO,WE,FR",
             "is_detached": False, "occurrence_date": "2026-07-01T09:00:00"},
        ])
        result = self.connector.get_events("Work", "2026-07-01", "2026-07-02")
        event = result[0]
        assert event["is_recurring"] is True
        assert "FREQ=WEEKLY" in event["recurrence_rule"]
        assert event["is_detached"] is False
        assert event["occurrence_date"] == "2026-07-01T09:00:00"

    @patch("apple_calendar_mcp.calendar_connector.run_swift_helper")
    def test_attendees_returned(self, mock_swift):
        mock_swift.return_value = json.dumps([
            {"uid": "ATT-123", "summary": "Team Meeting", "start_date": "2026-07-01T14:00:00",
             "end_date": "2026-07-01T15:00:00", "allday_event": False, "location": "",
             "notes": "", "url": "", "status": "confirmed", "calendar_name": "Work",
             "is_recurring": False, "recurrence_rule": None, "is_detached": False,
             "occurrence_date": "2026-07-01T14:00:00",
             "attendees": [
                 {"name": "Alice", "email": "alice@example.com", "role": "required", "status": "accepted"},
                 {"name": "", "email": "bob@example.com", "role": "optional", "status": "pending"},
             ]},
        ])
        result = self.connector.get_events("Work", "2026-07-01", "2026-07-02")
        event = result[0]
        assert len(event["attendees"]) == 2
        assert event["attendees"][0]["name"] == "Alice"
        assert event["attendees"][0]["email"] == "alice@example.com"
        assert event["attendees"][1]["role"] == "optional"

    @patch("apple_calendar_mcp.calendar_connector.run_swift_helper")
    def test_empty_attendees_returned(self, mock_swift):
        mock_swift.return_value = json.dumps([
            {"uid": "NO-ATT", "summary": "Solo Event", "start_date": "2026-07-01T10:00:00",
             "end_date": "2026-07-01T11:00:00", "allday_event": False, "location": "",
             "notes": "", "url": "", "status": "confirmed", "calendar_name": "Work",
             "is_recurring": False, "recurrence_rule": None, "is_detached": False,
             "occurrence_date": "2026-07-01T10:00:00", "attendees": []},
        ])
        result = self.connector.get_events("Work", "2026-07-01", "2026-07-02")
        assert result[0]["attendees"] == []


# ── get_availability ────────────────────────────────────────────────────────


class TestGetAvailability:
    """Tests for CalendarConnector.get_availability()."""

    def setup_method(self):
        self.connector = CalendarConnector()

    def _make_event(self, start, end, allday=False, calendar="Work"):
        return {
            "uid": "UID-1", "summary": "Event", "start_date": start,
            "end_date": end, "allday_event": allday, "location": "",
            "notes": "", "url": "", "status": "confirmed",
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
        def swift_side_effect(script_name, args, stdin_data=None):
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
        def swift_side_effect(script_name, args, stdin_data=None):
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

    @patch("apple_calendar_mcp.calendar_connector.run_swift_helper")
    def test_free_events_do_not_block_availability(self, mock_swift):
        """Events with availability='free' should not reduce available time."""
        event = self._make_event("2026-03-15T10:00:00", "2026-03-15T11:00:00")
        event["availability"] = "free"
        mock_swift.return_value = json.dumps([event])
        result = self.connector.get_availability(
            ["Work"], "2026-03-15T09:00:00", "2026-03-15T17:00:00"
        )
        # Entire range should be free since the event is marked "free"
        assert len(result) == 1
        assert result[0]["duration_minutes"] == 480


# ── get_availability: smart filtering ──────────────────────────────────────


class TestGetAvailabilityFiltering:
    """Tests for get_availability min_duration and working_hours params."""

    def setup_method(self):
        self.connector = CalendarConnector()

    def _make_event(self, start, end):
        return {
            "uid": "UID-1", "summary": "Event", "start_date": start,
            "end_date": end, "allday_event": False, "location": "",
            "notes": "", "url": "", "status": "confirmed",
            "calendar_name": "Work",
        }

    @patch("apple_calendar_mcp.calendar_connector.run_swift_helper")
    def test_min_duration_filters_short_slots(self, mock_swift):
        """Slots shorter than min_duration_minutes are excluded."""
        mock_swift.return_value = json.dumps([
            self._make_event("2026-03-15T10:00:00", "2026-03-15T10:30:00"),
            self._make_event("2026-03-15T12:00:00", "2026-03-15T13:00:00"),
        ])
        result = self.connector.get_availability(
            ["Work"], "2026-03-15T09:00:00", "2026-03-15T17:00:00",
            min_duration_minutes=45,
        )
        # 9:00-10:00 (60m) ✓, 10:30-12:00 (90m) ✓, 13:00-17:00 (240m) ✓
        assert len(result) == 3
        assert all(s["duration_minutes"] >= 45 for s in result)

    @patch("apple_calendar_mcp.calendar_connector.run_swift_helper")
    def test_min_duration_excludes_all(self, mock_swift):
        """All slots shorter than threshold → empty result."""
        mock_swift.return_value = json.dumps([
            self._make_event("2026-03-15T09:30:00", "2026-03-15T10:00:00"),
        ])
        result = self.connector.get_availability(
            ["Work"], "2026-03-15T09:00:00", "2026-03-15T10:30:00",
            min_duration_minutes=60,
        )
        # 9:00-9:30 (30m) ✗, 10:00-10:30 (30m) ✗
        assert len(result) == 0

    @patch("apple_calendar_mcp.calendar_connector.run_swift_helper")
    def test_working_hours_clips_single_day(self, mock_swift):
        """Free slot clipped to working hours window."""
        mock_swift.return_value = "[]"
        result = self.connector.get_availability(
            ["Work"], "2026-03-15T00:00:00", "2026-03-16T00:00:00",
            working_hours_start="09:00", working_hours_end="17:00",
        )
        assert len(result) == 1
        assert result[0]["start_date"] == "2026-03-15T09:00:00"
        assert result[0]["end_date"] == "2026-03-15T17:00:00"
        assert result[0]["duration_minutes"] == 480

    @patch("apple_calendar_mcp.calendar_connector.run_swift_helper")
    def test_working_hours_clips_partial_overlap(self, mock_swift):
        """Slot starting before working hours gets clipped to start."""
        mock_swift.return_value = json.dumps([
            self._make_event("2026-03-15T12:00:00", "2026-03-15T13:00:00"),
        ])
        result = self.connector.get_availability(
            ["Work"], "2026-03-15T06:00:00", "2026-03-15T20:00:00",
            working_hours_start="09:00", working_hours_end="17:00",
        )
        # 6:00-12:00 clipped to 9:00-12:00 (180m), 13:00-20:00 clipped to 13:00-17:00 (240m)
        assert len(result) == 2
        assert result[0]["start_date"] == "2026-03-15T09:00:00"
        assert result[0]["end_date"] == "2026-03-15T12:00:00"
        assert result[0]["duration_minutes"] == 180
        assert result[1]["start_date"] == "2026-03-15T13:00:00"
        assert result[1]["end_date"] == "2026-03-15T17:00:00"
        assert result[1]["duration_minutes"] == 240

    @patch("apple_calendar_mcp.calendar_connector.run_swift_helper")
    def test_working_hours_slot_outside_window(self, mock_swift):
        """Slot entirely outside working hours is excluded."""
        mock_swift.return_value = json.dumps([
            self._make_event("2026-03-15T09:00:00", "2026-03-15T17:00:00"),
        ])
        result = self.connector.get_availability(
            ["Work"], "2026-03-15T06:00:00", "2026-03-15T20:00:00",
            working_hours_start="09:00", working_hours_end="17:00",
        )
        # 6:00-9:00 outside WH, 17:00-20:00 outside WH → both excluded
        assert len(result) == 0

    @patch("apple_calendar_mcp.calendar_connector.run_swift_helper")
    def test_working_hours_multi_day_split(self, mock_swift):
        """Multi-day free slot split into per-day working hour windows."""
        mock_swift.return_value = "[]"
        result = self.connector.get_availability(
            ["Work"], "2026-03-15T00:00:00", "2026-03-18T00:00:00",
            working_hours_start="09:00", working_hours_end="17:00",
        )
        # 3 days: Mar 15, 16, 17 → 3 slots of 8h each
        assert len(result) == 3
        assert result[0]["start_date"] == "2026-03-15T09:00:00"
        assert result[0]["end_date"] == "2026-03-15T17:00:00"
        assert result[1]["start_date"] == "2026-03-16T09:00:00"
        assert result[2]["start_date"] == "2026-03-17T09:00:00"
        assert all(s["duration_minutes"] == 480 for s in result)

    @patch("apple_calendar_mcp.calendar_connector.run_swift_helper")
    def test_combined_working_hours_and_min_duration(self, mock_swift):
        """Working hours clip first, then min_duration filters remainders."""
        mock_swift.return_value = json.dumps([
            self._make_event("2026-03-15T09:00:00", "2026-03-15T09:30:00"),
            self._make_event("2026-03-15T12:00:00", "2026-03-15T16:45:00"),
        ])
        result = self.connector.get_availability(
            ["Work"], "2026-03-15T06:00:00", "2026-03-15T20:00:00",
            min_duration_minutes=30,
            working_hours_start="09:00", working_hours_end="17:00",
        )
        # After WH clip: 9:30-12:00 (150m) ✓, 16:45-17:00 (15m) ✗
        assert len(result) == 1
        assert result[0]["start_date"] == "2026-03-15T09:30:00"
        assert result[0]["duration_minutes"] == 150

    def test_working_hours_start_only_raises(self):
        with pytest.raises(ValueError, match="Both working_hours"):
            self.connector.get_availability(
                ["Work"], "2026-03-15T09:00:00", "2026-03-15T17:00:00",
                working_hours_start="09:00",
            )

    def test_working_hours_end_only_raises(self):
        with pytest.raises(ValueError, match="Both working_hours"):
            self.connector.get_availability(
                ["Work"], "2026-03-15T09:00:00", "2026-03-15T17:00:00",
                working_hours_end="17:00",
            )

    def test_invalid_time_format_raises(self):
        with pytest.raises(ValueError, match="Invalid time format"):
            self.connector.get_availability(
                ["Work"], "2026-03-15T09:00:00", "2026-03-15T17:00:00",
                working_hours_start="9am", working_hours_end="5pm",
            )

    def test_working_hours_start_after_end_raises(self):
        with pytest.raises(ValueError, match="must be before"):
            self.connector.get_availability(
                ["Work"], "2026-03-15T09:00:00", "2026-03-15T17:00:00",
                working_hours_start="17:00", working_hours_end="09:00",
            )

    def test_min_duration_zero_raises(self):
        with pytest.raises(ValueError, match="positive integer"):
            self.connector.get_availability(
                ["Work"], "2026-03-15T09:00:00", "2026-03-15T17:00:00",
                min_duration_minutes=0,
            )

    def test_min_duration_negative_raises(self):
        with pytest.raises(ValueError, match="positive integer"):
            self.connector.get_availability(
                ["Work"], "2026-03-15T09:00:00", "2026-03-15T17:00:00",
                min_duration_minutes=-10,
            )


class TestGetConflicts:
    """Tests for CalendarConnector.get_conflicts()."""

    def setup_method(self):
        self.connector = CalendarConnector(enable_safety_checks=False)

    def _make_event(self, uid, summary, start, end, calendar="Work", availability="busy", allday=False):
        return {
            "uid": uid, "summary": summary,
            "start_date": start, "end_date": end,
            "calendar_name": calendar, "availability": availability,
            "allday_event": allday,
        }

    @patch.object(CalendarConnector, "get_events")
    def test_no_events_returns_empty(self, mock_get):
        mock_get.return_value = []
        result = self.connector.get_conflicts(["Work"], "2026-03-15", "2026-03-16")
        assert result == []

    @patch.object(CalendarConnector, "get_events")
    def test_no_overlap_returns_empty(self, mock_get):
        mock_get.return_value = [
            self._make_event("A", "Meeting", "2026-03-15T10:00:00", "2026-03-15T11:00:00"),
            self._make_event("B", "Lunch", "2026-03-15T12:00:00", "2026-03-15T13:00:00"),
        ]
        result = self.connector.get_conflicts(["Work"], "2026-03-15", "2026-03-16")
        assert result == []

    @patch.object(CalendarConnector, "get_events")
    def test_simple_overlap(self, mock_get):
        mock_get.return_value = [
            self._make_event("A", "Meeting", "2026-03-15T10:00:00", "2026-03-15T11:00:00"),
            self._make_event("B", "Call", "2026-03-15T10:30:00", "2026-03-15T11:30:00"),
        ]
        result = self.connector.get_conflicts(["Work"], "2026-03-15", "2026-03-16")
        assert len(result) == 1
        assert result[0]["event_a"]["uid"] == "A"
        assert result[0]["event_b"]["uid"] == "B"
        assert result[0]["overlap_minutes"] == 30
        assert result[0]["overlap_start"] == "2026-03-15T10:30:00"
        assert result[0]["overlap_end"] == "2026-03-15T11:00:00"

    @patch.object(CalendarConnector, "get_events")
    def test_three_way_overlap(self, mock_get):
        mock_get.return_value = [
            self._make_event("A", "Meeting", "2026-03-15T10:00:00", "2026-03-15T11:00:00"),
            self._make_event("B", "Call", "2026-03-15T10:00:00", "2026-03-15T11:00:00"),
            self._make_event("C", "Review", "2026-03-15T10:30:00", "2026-03-15T11:30:00"),
        ]
        result = self.connector.get_conflicts(["Work"], "2026-03-15", "2026-03-16")
        assert len(result) == 3  # A-B, A-C, B-C

    @patch.object(CalendarConnector, "get_events")
    def test_free_events_excluded(self, mock_get):
        mock_get.return_value = [
            self._make_event("A", "Meeting", "2026-03-15T10:00:00", "2026-03-15T11:00:00", availability="busy"),
            self._make_event("B", "Lunch", "2026-03-15T10:30:00", "2026-03-15T11:30:00", availability="free"),
        ]
        result = self.connector.get_conflicts(["Work"], "2026-03-15", "2026-03-16")
        assert result == []

    @patch.object(CalendarConnector, "get_events")
    def test_tentative_events_included(self, mock_get):
        mock_get.return_value = [
            self._make_event("A", "Meeting", "2026-03-15T10:00:00", "2026-03-15T11:00:00", availability="busy"),
            self._make_event("B", "Maybe", "2026-03-15T10:30:00", "2026-03-15T11:30:00", availability="tentative"),
        ]
        result = self.connector.get_conflicts(["Work"], "2026-03-15", "2026-03-16")
        assert len(result) == 1

    @patch.object(CalendarConnector, "get_events")
    def test_multi_calendar(self, mock_get):
        def side_effect(cal_name, start, end):
            if cal_name == "Work":
                return [self._make_event("A", "Meeting", "2026-03-15T10:00:00", "2026-03-15T11:00:00", "Work")]
            return [self._make_event("B", "Dentist", "2026-03-15T10:30:00", "2026-03-15T11:30:00", "Personal")]
        mock_get.side_effect = side_effect
        result = self.connector.get_conflicts(["Work", "Personal"], "2026-03-15", "2026-03-16")
        assert len(result) == 1
        assert result[0]["event_a"]["calendar_name"] == "Work"
        assert result[0]["event_b"]["calendar_name"] == "Personal"

    @patch.object(CalendarConnector, "get_events")
    def test_adjacent_events_no_conflict(self, mock_get):
        mock_get.return_value = [
            self._make_event("A", "Meeting", "2026-03-15T10:00:00", "2026-03-15T11:00:00"),
            self._make_event("B", "Call", "2026-03-15T11:00:00", "2026-03-15T12:00:00"),
        ]
        result = self.connector.get_conflicts(["Work"], "2026-03-15", "2026-03-16")
        assert result == []

    def test_empty_calendar_list_raises(self):
        with pytest.raises(ValueError, match="At least one calendar"):
            self.connector.get_conflicts([], "2026-03-15", "2026-03-16")


class TestParseTimeString:
    """Tests for CalendarConnector._parse_time_string()."""

    def test_valid_time(self):
        assert CalendarConnector._parse_time_string("09:00") == (9, 0)
        assert CalendarConnector._parse_time_string("17:30") == (17, 30)
        assert CalendarConnector._parse_time_string("00:00") == (0, 0)
        assert CalendarConnector._parse_time_string("23:59") == (23, 59)

    def test_invalid_format(self):
        with pytest.raises(ValueError, match="Invalid time format"):
            CalendarConnector._parse_time_string("9am")

    def test_out_of_range_hour(self):
        with pytest.raises(ValueError, match="Hour must be 0-23"):
            CalendarConnector._parse_time_string("25:00")

    def test_out_of_range_minute(self):
        with pytest.raises(ValueError, match="minute must be 0-59"):
            CalendarConnector._parse_time_string("09:60")


# ── update_event ────────────────────────────────────────────────────────────


class TestUpdateEvent:
    """Tests for CalendarConnector.update_event()."""

    def setup_method(self):
        self.connector = CalendarConnector(enable_safety_checks=False)

    @patch("apple_calendar_mcp.calendar_connector.run_swift_helper")
    def test_updates_summary(self, mock_swift):
        mock_swift.return_value = json.dumps({"uid": "ABC-123", "updated_fields": ["summary"]})
        self.connector.update_event("MCP-Test-Calendar", "ABC-123", summary="New Title")
        args = mock_swift.call_args[0][1]
        assert "--summary" in args
        assert "New Title" in args

    @patch("apple_calendar_mcp.calendar_connector.run_swift_helper")
    def test_updates_dates(self, mock_swift):
        mock_swift.return_value = json.dumps({"uid": "ABC-123", "updated_fields": ["start_date", "end_date"]})
        self.connector.update_event("MCP-Test-Calendar", "ABC-123",
                                    start_date="2026-03-15T14:30:00", end_date="2026-03-15T15:30:00")
        args = mock_swift.call_args[0][1]
        assert "--start" in args
        assert "2026-03-15T14:30:00" in args
        assert "--end" in args
        assert "2026-03-15T15:30:00" in args

    @patch("apple_calendar_mcp.calendar_connector.run_swift_helper")
    def test_updates_allday(self, mock_swift):
        mock_swift.return_value = json.dumps({"uid": "ABC-123", "updated_fields": ["allday_event"]})
        self.connector.update_event("MCP-Test-Calendar", "ABC-123", allday_event=True)
        args = mock_swift.call_args[0][1]
        assert "--allday" in args
        assert "true" in args

    @patch("apple_calendar_mcp.calendar_connector.run_swift_helper")
    def test_updates_multiple_fields(self, mock_swift):
        mock_swift.return_value = json.dumps({"uid": "ABC-123", "updated_fields": ["summary", "location"]})
        result = self.connector.update_event("MCP-Test-Calendar", "ABC-123", summary="New", location="Room C")
        args = mock_swift.call_args[0][1]
        assert "--summary" in args
        assert "--location" in args
        assert result == {"uid": "ABC-123", "updated_fields": ["summary", "location"]}

    @patch("apple_calendar_mcp.calendar_connector.run_swift_helper")
    def test_only_provided_fields_passed(self, mock_swift):
        mock_swift.return_value = json.dumps({"uid": "ABC-123", "updated_fields": ["summary"]})
        self.connector.update_event("MCP-Test-Calendar", "ABC-123", summary="New Title")
        args = mock_swift.call_args[0][1]
        assert "--summary" in args
        assert "--location" not in args
        assert "--description" not in args
        assert "--url" not in args
        assert "--start" not in args
        assert "--end" not in args
        assert "--allday" not in args

    @patch("apple_calendar_mcp.calendar_connector.run_swift_helper")
    def test_clear_field_with_empty_string(self, mock_swift):
        mock_swift.return_value = json.dumps({"uid": "ABC-123", "updated_fields": ["location"]})
        self.connector.update_event("MCP-Test-Calendar", "ABC-123", location="")
        args = mock_swift.call_args[0][1]
        assert "--clear-location" in args
        assert "--location" not in args

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

    @patch("apple_calendar_mcp.calendar_connector.run_swift_helper")
    def test_event_not_found_raises(self, mock_swift):
        mock_swift.return_value = json.dumps({"error": "event_not_found", "message": "Event not found: BAD-UID"})
        with pytest.raises(ValueError, match="Event not found"):
            self.connector.update_event("MCP-Test-Calendar", "BAD-UID", summary="X")

    @patch("apple_calendar_mcp.calendar_connector.run_swift_helper")
    def test_passes_occurrence_date(self, mock_swift):
        mock_swift.return_value = json.dumps({"uid": "REC-123", "updated_fields": ["summary"]})
        self.connector.update_event("MCP-Test-Calendar", "REC-123",
                                    summary="Modified", occurrence_date="2027-01-05T10:00:00")
        args = mock_swift.call_args[0][1]
        assert "--occurrence-date" in args
        assert "2027-01-05T10:00:00" in args

    @patch("apple_calendar_mcp.calendar_connector.run_swift_helper")
    def test_passes_span_future_events(self, mock_swift):
        mock_swift.return_value = json.dumps({"uid": "REC-123", "updated_fields": ["summary"]})
        self.connector.update_event("MCP-Test-Calendar", "REC-123",
                                    summary="Series Update", span="future_events")
        args = mock_swift.call_args[0][1]
        assert "--span" in args
        assert "future_events" in args

    @patch("apple_calendar_mcp.calendar_connector.run_swift_helper")
    def test_default_span_not_passed(self, mock_swift):
        mock_swift.return_value = json.dumps({"uid": "ABC-123", "updated_fields": ["summary"]})
        self.connector.update_event("MCP-Test-Calendar", "ABC-123", summary="X")
        args = mock_swift.call_args[0][1]
        assert "--span" not in args
        assert "--occurrence-date" not in args


# ── delete_events ──────────────────────────────────────────────────────────


class TestDeleteEvents:
    """Tests for CalendarConnector.delete_events()."""

    def setup_method(self):
        self.connector = CalendarConnector(enable_safety_checks=False)

    @patch("apple_calendar_mcp.calendar_connector.run_swift_helper")
    def test_deletes_single_event(self, mock_swift):
        mock_swift.return_value = json.dumps({"deleted_uids": ["ABC-123"], "not_found_uids": []})
        result = self.connector.delete_events("MCP-Test-Calendar", "ABC-123")
        assert result["deleted_uids"] == ["ABC-123"]
        assert result["not_found_uids"] == []
        args = mock_swift.call_args[0][1]
        assert "--uid" in args
        assert "ABC-123" in args

    @patch("apple_calendar_mcp.calendar_connector.run_swift_helper")
    def test_deletes_multiple_events(self, mock_swift):
        mock_swift.return_value = json.dumps({"deleted_uids": ["UID-1", "UID-2", "UID-3"], "not_found_uids": []})
        result = self.connector.delete_events("MCP-Test-Calendar", ["UID-1", "UID-2", "UID-3"])
        assert result["deleted_uids"] == ["UID-1", "UID-2", "UID-3"]
        args = mock_swift.call_args[0][1]
        # All UIDs passed in single call
        assert args.count("--uid") == 3

    @patch("apple_calendar_mcp.calendar_connector.run_swift_helper")
    def test_normalizes_single_uid_to_list(self, mock_swift):
        mock_swift.return_value = json.dumps({"deleted_uids": ["SINGLE-UID"], "not_found_uids": []})
        result = self.connector.delete_events("MCP-Test-Calendar", "SINGLE-UID")
        assert isinstance(result["deleted_uids"], list)
        assert result["deleted_uids"] == ["SINGLE-UID"]

    def test_safety_blocks_non_test_calendar(self):
        connector = CalendarConnector(enable_safety_checks=True)
        with pytest.raises(CalendarSafetyError, match="not an allowed test calendar"):
            connector.delete_events("Personal", "ABC-123")

    def test_empty_list_raises(self):
        with pytest.raises(ValueError, match="At least one event UID"):
            self.connector.delete_events("MCP-Test-Calendar", [])

    @patch("apple_calendar_mcp.calendar_connector.run_swift_helper")
    def test_not_found_uid(self, mock_swift):
        mock_swift.return_value = json.dumps({"deleted_uids": [], "not_found_uids": ["BAD-UID"]})
        result = self.connector.delete_events("MCP-Test-Calendar", "BAD-UID")
        assert result["deleted_uids"] == []
        assert result["not_found_uids"] == ["BAD-UID"]

    @patch("apple_calendar_mcp.calendar_connector.run_swift_helper")
    def test_batch_partial_failure(self, mock_swift):
        mock_swift.return_value = json.dumps({"deleted_uids": ["UID-1", "UID-3"], "not_found_uids": ["UID-2"]})
        result = self.connector.delete_events("MCP-Test-Calendar", ["UID-1", "UID-2", "UID-3"])
        assert result["deleted_uids"] == ["UID-1", "UID-3"]
        assert result["not_found_uids"] == ["UID-2"]

    @patch("apple_calendar_mcp.calendar_connector.run_swift_helper")
    def test_passes_span_future_events(self, mock_swift):
        mock_swift.return_value = json.dumps({"deleted_uids": ["REC-123"], "not_found_uids": []})
        self.connector.delete_events("MCP-Test-Calendar", "REC-123", span="future_events")
        args = mock_swift.call_args[0][1]
        assert "--span" in args
        assert "future_events" in args

    @patch("apple_calendar_mcp.calendar_connector.run_swift_helper")
    def test_default_span_not_passed(self, mock_swift):
        mock_swift.return_value = json.dumps({"deleted_uids": ["ABC-123"], "not_found_uids": []})
        self.connector.delete_events("MCP-Test-Calendar", "ABC-123")
        args = mock_swift.call_args[0][1]
        assert "--span" not in args


# ── _run_swift_helper_json error handling ─────────────────────────────────


class TestRunSwiftHelperJson:
    """Tests for CalendarConnector._run_swift_helper_json() error paths."""

    def setup_method(self):
        self.connector = CalendarConnector(enable_safety_checks=False)

    @patch("apple_calendar_mcp.calendar_connector.run_swift_helper")
    def test_called_process_error_with_json_stdout(self, mock_swift):
        """CalledProcessError with JSON error in stdout should map to correct exception."""
        error = subprocess.CalledProcessError(1, "swift")
        error.stdout = json.dumps({"error": "calendar_not_found", "message": "Calendar 'X' not found"})
        mock_swift.side_effect = error
        with pytest.raises(ValueError, match="Calendar 'X' not found"):
            self.connector._run_swift_helper_json("test_script", [])

    @patch("apple_calendar_mcp.calendar_connector.run_swift_helper")
    def test_called_process_error_with_no_output(self, mock_swift):
        """CalledProcessError with empty stdout should raise RuntimeError."""
        error = subprocess.CalledProcessError(1, "swift")
        error.stdout = ""
        mock_swift.side_effect = error
        with pytest.raises(RuntimeError, match="failed with no output"):
            self.connector._run_swift_helper_json("test_script", [])

    @patch("apple_calendar_mcp.calendar_connector.run_swift_helper")
    def test_called_process_error_with_none_stdout(self, mock_swift):
        """CalledProcessError with None stdout should raise RuntimeError."""
        error = subprocess.CalledProcessError(1, "swift")
        error.stdout = None
        mock_swift.side_effect = error
        with pytest.raises(RuntimeError, match="failed with no output"):
            self.connector._run_swift_helper_json("test_script", [])


# ── create_events (batch) ─────────────────────────────────────────────────


class TestCreateEvents:
    """Tests for CalendarConnector.create_events()."""

    def setup_method(self):
        self.connector = CalendarConnector(enable_safety_checks=False)

    @patch("apple_calendar_mcp.calendar_connector.run_swift_helper")
    def test_creates_batch_events(self, mock_swift):
        mock_swift.return_value = json.dumps({
            "created": [{"uid": "UID-1", "summary": "Event 1"}, {"uid": "UID-2", "summary": "Event 2"}],
            "errors": [],
        })
        events = [
            {"summary": "Event 1", "start": "2026-03-15T10:00:00", "end": "2026-03-15T11:00:00"},
            {"summary": "Event 2", "start": "2026-03-15T12:00:00", "end": "2026-03-15T13:00:00"},
        ]
        result = self.connector.create_events("MCP-Test-Calendar", events)
        assert len(result["created"]) == 2
        assert result["errors"] == []

    @patch("apple_calendar_mcp.calendar_connector.run_swift_helper")
    def test_partial_success(self, mock_swift):
        mock_swift.return_value = json.dumps({
            "created": [{"uid": "UID-1", "summary": "Event 1"}],
            "errors": [{"index": 1, "summary": "Bad Event", "error": "invalid date"}],
        })
        result = self.connector.create_events("MCP-Test-Calendar", [{"summary": "Event 1"}, {"summary": "Bad Event"}])
        assert len(result["created"]) == 1
        assert len(result["errors"]) == 1

    def test_empty_list_raises(self):
        with pytest.raises(ValueError, match="At least one event"):
            self.connector.create_events("MCP-Test-Calendar", [])

    def test_safety_blocks_non_test_calendar(self):
        connector = CalendarConnector(enable_safety_checks=True)
        with pytest.raises(CalendarSafetyError):
            connector.create_events("Personal", [{"summary": "Test"}])


# ── update_events (batch) ─────────────────────────────────────────────────


class TestUpdateEvents:
    """Tests for CalendarConnector.update_events()."""

    def setup_method(self):
        self.connector = CalendarConnector(enable_safety_checks=False)

    @patch("apple_calendar_mcp.calendar_connector.run_swift_helper")
    def test_updates_batch(self, mock_swift):
        mock_swift.return_value = json.dumps({
            "updated": [{"uid": "UID-1", "summary": "Updated", "updated_fields": ["summary"]}],
            "errors": [],
        })
        result = self.connector.update_events("MCP-Test-Calendar", [{"uid": "UID-1", "summary": "Updated"}])
        assert len(result["updated"]) == 1

    def test_empty_list_raises(self):
        with pytest.raises(ValueError, match="At least one update"):
            self.connector.update_events("MCP-Test-Calendar", [])

    def test_occurrence_date_rejected(self):
        with pytest.raises(ValueError, match="does not support occurrence_date"):
            self.connector.update_events("MCP-Test-Calendar", [{"uid": "UID-1", "occurrence_date": "2026-03-15"}])

    def test_safety_blocks_non_test_calendar(self):
        connector = CalendarConnector(enable_safety_checks=True)
        with pytest.raises(CalendarSafetyError):
            connector.update_events("Personal", [{"uid": "UID-1", "summary": "Test"}])


# ── search_events ─────────────────────────────────────────────────────────


class TestSearchEvents:
    """Tests for CalendarConnector.search_events()."""

    def setup_method(self):
        self.connector = CalendarConnector(enable_safety_checks=False)

    @patch("apple_calendar_mcp.calendar_connector.run_swift_helper")
    def test_searches_specific_calendar(self, mock_swift):
        mock_swift.return_value = json.dumps([
            {"uid": "UID-1", "summary": "Team Lunch", "start_date": "2026-03-15T12:00:00",
             "end_date": "2026-03-15T13:00:00", "calendar_name": "Work"},
        ])
        results = self.connector.search_events("lunch", calendar_name="Work",
                                                start_date="2026-03-01", end_date="2026-04-01")
        assert len(results) == 1
        assert results[0]["summary"] == "Team Lunch"
        args = mock_swift.call_args[0][1]
        assert "--query" in args
        assert "lunch" in args

    @patch("apple_calendar_mcp.calendar_connector.run_swift_helper")
    def test_searches_all_calendars(self, mock_swift):
        """When no calendar_name, searches all calendars."""
        # get_calendars returns two calendars
        def side_effect(script, args, **kwargs):
            if script == "get_calendars":
                return json.dumps([
                    {"name": "Work", "writable": True, "description": "", "color": "#FF0000", "source": "iCloud"},
                    {"name": "Personal", "writable": True, "description": "", "color": "#0000FF"},
                ])
            # get_events returns for each calendar
            return json.dumps([])
        mock_swift.side_effect = side_effect
        results = self.connector.search_events("lunch", start_date="2026-03-01", end_date="2026-04-01")
        assert results == []
        # Should have called get_calendars + get_events for each calendar
        assert mock_swift.call_count == 3  # get_calendars + 2x get_events

    @patch("apple_calendar_mcp.calendar_connector.run_swift_helper")
    def test_default_date_range(self, mock_swift):
        """When no dates, defaults to 1 month ago to 6 months from now."""
        mock_swift.return_value = json.dumps([])
        self.connector.search_events("test", calendar_name="Work")
        args = mock_swift.call_args[0][1]
        # Should have --start and --end with auto-generated dates
        assert "--start" in args
        assert "--end" in args

    @patch("apple_calendar_mcp.calendar_connector.run_swift_helper")
    def test_skips_calendar_not_found(self, mock_swift):
        """Calendar not found errors should be silently skipped."""
        def side_effect(script, args, **kwargs):
            if script == "get_calendars":
                return json.dumps([
                    {"name": "Work", "writable": True, "description": "", "color": "#FF0000", "source": "iCloud"},
                    {"name": "Missing", "writable": True, "description": "", "color": "#00FF00"},
                ])
            # Work returns events, Missing raises ValueError
            cal_arg_idx = args.index("--calendar") + 1 if "--calendar" in args else -1
            if cal_arg_idx >= 0 and args[cal_arg_idx] == "Missing":
                return json.dumps({"error": "calendar_not_found", "message": "not found"})
            return json.dumps([{"uid": "UID-1", "summary": "Found", "start_date": "2026-03-15T10:00:00",
                                "end_date": "2026-03-15T11:00:00", "calendar_name": "Work"}])
        mock_swift.side_effect = side_effect
        results = self.connector.search_events("found", start_date="2026-03-01", end_date="2026-04-01")
        assert len(results) == 1
