"""Client for interacting with Apple Calendar app."""
import subprocess
import json
import os
from datetime import datetime, timedelta
from pathlib import Path
from typing import Any, Optional


def run_applescript(script: str, timeout: int = 60) -> str:
    """Execute AppleScript and return the result.

    Args:
        script: The AppleScript code to execute
        timeout: Maximum seconds to wait (default: 60, max: 300)

    Returns:
        The stdout output from the AppleScript

    Raises:
        subprocess.TimeoutExpired: If script execution exceeds timeout
        subprocess.CalledProcessError: If script execution fails
    """
    if timeout > 300:
        raise ValueError("Timeout cannot exceed 300 seconds")

    result = subprocess.run(
        ["osascript", "-e", script],
        capture_output=True,
        text=True,
        check=True,
        timeout=timeout,
    )
    return result.stdout.strip()


def run_swift_helper(script_name: str, args: list[str], timeout: int = 30) -> str:
    """Execute a Swift helper script and return the result.

    Args:
        script_name: Name of the Swift script (without .swift extension)
        args: Command-line arguments to pass to the script
        timeout: Maximum seconds to wait (default: 30)

    Returns:
        The stdout output from the Swift script

    Raises:
        subprocess.TimeoutExpired: If script execution exceeds timeout
        subprocess.CalledProcessError: If script execution fails
    """
    script_path = Path(__file__).parent / "swift" / f"{script_name}.swift"
    result = subprocess.run(
        ["swift", str(script_path)] + args,
        capture_output=True,
        text=True,
        check=True,
        timeout=timeout,
    )
    return result.stdout.strip()



class CalendarSafetyError(Exception):
    """Raised when calendar safety checks fail."""
    pass


class CalendarConnector:
    """Client for Apple Calendar app operations using AppleScript.

    SAFETY: For integration testing with real Calendar, set environment variables:
        CALENDAR_TEST_MODE=true
        CALENDAR_TEST_NAME=MCP-Test-Calendar

    Without these, destructive operations will be blocked to protect your calendars.
    """

    ALLOWED_TEST_CALENDARS = {
        "MCP-Test-Calendar",
        "MCP-Test-Calendar-2",
    }

    def __init__(self, enable_safety_checks: bool = True):
        self.enable_safety_checks = enable_safety_checks

    def _verify_calendar_safety(self, calendar_name: str) -> None:
        """Verify that a write operation targets an allowed test calendar.

        Raises:
            CalendarSafetyError: If safety checks are enabled and the calendar
                is not in the allowed test calendar list.
        """
        if not self.enable_safety_checks:
            return
        if calendar_name not in self.ALLOWED_TEST_CALENDARS:
            raise CalendarSafetyError(
                f"Calendar '{calendar_name}' is not an allowed test calendar. "
                f"Allowed: {self.ALLOWED_TEST_CALENDARS}"
            )

    def _escape_applescript_string(self, text: Optional[str]) -> str:
        """Escape quotes and backslashes for AppleScript strings."""
        if not text:
            return ""
        text = text.replace("\\", "\\\\")
        text = text.replace('"', '\\"')
        return text

    def _iso_to_applescript_date(self, iso_date: str) -> str:
        """Convert ISO 8601 date to AppleScript date format.

        Args:
            iso_date: Date in ISO 8601 format (e.g., "2026-03-15" or "2026-03-15T14:30:00")

        Returns:
            str: Date in AppleScript format (e.g., "March 15, 2026 02:30:00 PM")
        """
        try:
            if "T" in iso_date:
                dt = datetime.fromisoformat(iso_date.replace("Z", "+00:00"))
            else:
                dt = datetime.fromisoformat(iso_date + "T00:00:00")
        except ValueError as e:
            raise ValueError(
                f"Invalid date format '{iso_date}'. "
                "Expected ISO 8601 format like '2026-03-15' or '2026-03-15T14:30:00'"
            ) from e

        # Format for AppleScript: "March 15, 2026 02:30:00 PM"
        return dt.strftime("%B %d, %Y %I:%M:%S %p")

    def _run_swift_helper_json(self, script_name: str, args: list[str]) -> dict:
        """Run a Swift helper and parse JSON response, raising on errors."""
        result = run_swift_helper(script_name, args)
        parsed = json.loads(result)
        if isinstance(parsed, dict) and "error" in parsed:
            error_map = {
                "calendar_access_denied": PermissionError,
                "calendar_not_found": ValueError,
                "event_not_found": ValueError,
            }
            exc_type = error_map.get(parsed["error"], RuntimeError)
            raise exc_type(parsed["message"])
        return parsed

    def create_event(
        self,
        calendar_name: str,
        summary: str,
        start_date: str,
        end_date: str,
        location: Optional[str] = None,
        description: Optional[str] = None,
        url: Optional[str] = None,
        allday_event: bool = False,
        recurrence_rule: Optional[str] = None,
        alert_minutes: Optional[list[int]] = None,
        availability: Optional[str] = None,
    ) -> str:
        """Create a new event in a specified calendar.

        Args:
            calendar_name: Name of the target calendar
            summary: Event title
            start_date: Start date/time in ISO 8601 format
            end_date: End date/time in ISO 8601 format
            location: Event location (optional)
            description: Event notes (optional)
            url: URL associated with the event (optional)
            allday_event: Whether this is an all-day event
            recurrence_rule: iCalendar RRULE string (optional, e.g. "FREQ=WEEKLY;BYDAY=MO,WE,FR")
            alert_minutes: List of alert times in minutes before event (optional, e.g. [15, 60])

        Returns:
            The UID of the created event

        Raises:
            CalendarSafetyError: If safety checks block the target calendar
            ValueError: If date format is invalid
            subprocess.CalledProcessError: If AppleScript execution fails
        """
        self._verify_calendar_safety(calendar_name)
        self._validate_date(start_date)
        self._validate_date(end_date)

        args = ["--calendar", calendar_name, "--summary", summary,
                "--start", start_date, "--end", end_date]
        if location:
            args += ["--location", location]
        if description:
            args += ["--description", description]
        if url:
            args += ["--url", url]
        if allday_event:
            args += ["--allday"]
        if recurrence_rule:
            args += ["--recurrence", recurrence_rule]
        if alert_minutes:
            for mins in alert_minutes:
                args += ["--alert", str(mins)]
        if availability:
            args += ["--availability", availability]

        parsed = self._run_swift_helper_json("create_event", args)
        return parsed["uid"]

    def _validate_date(self, date_str: str) -> None:
        """Validate that a string is a valid ISO 8601 date.

        Raises:
            ValueError: If the date format is invalid.
        """
        try:
            if "T" in date_str:
                datetime.fromisoformat(date_str.replace("Z", "+00:00"))
            else:
                datetime.fromisoformat(date_str + "T00:00:00")
        except ValueError as e:
            raise ValueError(
                f"Invalid date format '{date_str}'. "
                "Expected ISO 8601 format like '2026-03-15' or '2026-03-15T14:30:00'"
            ) from e

    def get_events(
        self,
        calendar_name: str,
        start_date: str,
        end_date: str,
    ) -> list[dict[str, Any]]:
        """Get events from a calendar within a date range.

        Uses EventKit via Swift helper for fast native date-range queries.

        Args:
            calendar_name: Name of the calendar to query
            start_date: Start of date range in ISO 8601 format
            end_date: End of date range in ISO 8601 format

        Returns:
            List of event dicts with keys: uid, summary, start_date, end_date,
            allday_event, location, description, url, status, calendar_name.

        Raises:
            ValueError: If date format is invalid or calendar not found
            PermissionError: If EventKit calendar access is denied
        """
        self._validate_date(start_date)
        self._validate_date(end_date)

        args = ["--calendar", calendar_name, "--start", start_date, "--end", end_date]
        return self._run_swift_helper_json("get_events", args)

    def search_events(
        self,
        query: str,
        calendar_name: Optional[str] = None,
        start_date: Optional[str] = None,
        end_date: Optional[str] = None,
    ) -> list[dict[str, Any]]:
        """Search events by text across one or all calendars.

        Searches event summaries, descriptions, and locations with
        case-insensitive matching.

        Args:
            query: Text to search for
            calendar_name: Calendar to search (optional — searches all if omitted)
            start_date: Start of date range (optional — defaults to 1 month ago)
            end_date: End of date range (optional — defaults to 6 months from now)

        Returns:
            List of matching event dicts.
        """
        if not start_date:
            start_date = (datetime.now() - timedelta(days=30)).strftime("%Y-%m-%dT00:00:00")
        if not end_date:
            end_date = (datetime.now() + timedelta(days=180)).strftime("%Y-%m-%dT00:00:00")

        self._validate_date(start_date)
        self._validate_date(end_date)

        if calendar_name:
            calendars = [calendar_name]
        else:
            cal_list = self.get_calendars()
            calendars = [c["name"] for c in cal_list]

        all_results = []
        for cal in calendars:
            args = ["--calendar", cal, "--start", start_date, "--end", end_date, "--query", query]
            try:
                events = self._run_swift_helper_json("get_events", args)
                if isinstance(events, list):
                    all_results.extend(events)
            except ValueError:
                continue  # skip calendars that error (e.g., not found)

        return all_results

    def update_event(
        self,
        calendar_name: str,
        event_uid: str,
        summary: str | None = None,
        start_date: str | None = None,
        end_date: str | None = None,
        location: str | None = None,
        description: str | None = None,
        url: str | None = None,
        allday_event: bool | None = None,
        alert_minutes: list[int] | None = None,
        availability: str | None = None,
        recurrence_rule: str | None = None,
        occurrence_date: str | None = None,
        span: str = "this_event",
    ) -> dict[str, Any]:
        """Update an existing event's properties by UID.

        Only provided fields are updated; omitted fields (None) are left unchanged.
        Pass an empty string to clear a text field. Pass empty string for recurrence_rule to remove recurrence.

        Args:
            calendar_name: Name of the calendar containing the event
            event_uid: UID of the event to update
            summary: New event title (optional)
            start_date: New start date/time in ISO 8601 format (optional)
            end_date: New end date/time in ISO 8601 format (optional)
            location: New location (optional, "" to clear)
            description: New description (optional, "" to clear)
            url: New URL (optional, "" to clear)
            allday_event: New all-day status (optional)
            occurrence_date: For recurring events, the date of the specific occurrence to update (optional)
            span: "this_event" to update one occurrence, "future_events" to update this and all future (default: "this_event")

        Returns:
            Dict with 'uid' and 'updated_fields' keys

        Raises:
            CalendarSafetyError: If safety checks block the target calendar
            ValueError: If no fields provided or date format is invalid
        """
        self._verify_calendar_safety(calendar_name)

        fields = {
            "summary": summary,
            "start_date": start_date,
            "end_date": end_date,
            "location": location,
            "description": description,
            "url": url,
            "allday_event": allday_event,
        }
        args, updated_fields = self._build_update_args(
            calendar_name, event_uid, fields, occurrence_date, span
        )

        if alert_minutes is not None:
            if len(alert_minutes) == 0:
                args += ["--clear-alerts"]
            else:
                for mins in alert_minutes:
                    args += ["--alert", str(mins)]
            updated_fields.append("alerts")

        if recurrence_rule is not None:
            if recurrence_rule == "":
                args += ["--clear-recurrence"]
            else:
                args += ["--recurrence", recurrence_rule]
            updated_fields.append("recurrence_rule")

        if availability is not None:
            args += ["--availability", availability]
            updated_fields.append("availability")

        if not updated_fields:
            raise ValueError("At least one field must be provided to update")

        self._run_swift_helper_json("update_event", args)
        return {"uid": event_uid, "updated_fields": updated_fields}

    def _build_update_args(
        self,
        calendar_name: str,
        event_uid: str,
        fields: dict,
        occurrence_date: str | None,
        span: str,
    ) -> tuple[list[str], list[str]]:
        """Build CLI args and updated_fields list for update_event Swift helper."""
        args = ["--calendar", calendar_name, "--uid", event_uid]
        updated_fields = []

        flag_map = {
            "summary": "--summary",
            "start_date": "--start",
            "end_date": "--end",
            "location": "--location",
            "description": "--description",
            "url": "--url",
        }
        clearable = {"location", "description", "url"}
        date_fields = {"start_date", "end_date"}

        for field_name, value in fields.items():
            if value is None:
                continue
            if field_name == "allday_event":
                args += ["--allday", "true" if value else "false"]
            elif field_name in clearable and value == "":
                args += [f"--clear-{field_name}"]
            else:
                if field_name in date_fields:
                    self._validate_date(value)
                args += [flag_map[field_name], value]
            updated_fields.append(field_name)

        if occurrence_date:
            args += ["--occurrence-date", occurrence_date]
        if span != "this_event":
            args += ["--span", span]

        return args, updated_fields

    def delete_events(
        self,
        calendar_name: str,
        event_uids: str | list[str],
        span: str = "this_event",
        occurrence_date: Optional[str] = None,
    ) -> dict[str, Any]:
        """Delete one or more events by UID.

        Args:
            calendar_name: Name of the calendar containing the events
            event_uids: Single UID string or list of UIDs to delete
            span: "this_event" to delete one occurrence, "future_events" to delete series from this point (default: "this_event")
            occurrence_date: For recurring events, the date of the specific occurrence to delete (optional)

        Returns:
            Dict with 'deleted_uids' and 'not_found_uids' keys

        Raises:
            CalendarSafetyError: If safety checks block the target calendar
            ValueError: If event_uids is empty
        """
        self._verify_calendar_safety(calendar_name)

        uids = [event_uids] if isinstance(event_uids, str) else event_uids
        if not uids:
            raise ValueError("At least one event UID must be provided")

        args = ["--calendar", calendar_name]
        for uid in uids:
            args += ["--uid", uid]
        if span != "this_event":
            args += ["--span", span]
        if occurrence_date:
            args += ["--occurrence-date", occurrence_date]

        parsed = self._run_swift_helper_json("delete_events", args)
        return {"deleted_uids": parsed["deleted_uids"], "not_found_uids": parsed["not_found_uids"]}

    def _parse_iso_datetime(self, date_str: str) -> datetime:
        """Parse an ISO 8601 date string to a naive local-time datetime.

        Timezone-aware dates (e.g., from EventKit's UTC output) are converted
        to local time before stripping tzinfo, so they can be compared with
        timezone-naive query dates.

        Raises:
            ValueError: If the date format is invalid.
        """
        try:
            if "T" in date_str:
                dt = datetime.fromisoformat(date_str.replace("Z", "+00:00"))
                if dt.tzinfo is not None:
                    dt = dt.astimezone().replace(tzinfo=None)
                return dt
            else:
                return datetime.fromisoformat(date_str + "T00:00:00")
        except ValueError as e:
            raise ValueError(
                f"Invalid date format '{date_str}'. "
                "Expected ISO 8601 format like '2026-03-15' or '2026-03-15T14:30:00'"
            ) from e

    def _build_busy_blocks(self, events: list[dict]) -> list[tuple[datetime, datetime]]:
        """Build sorted, merged busy blocks from a list of events."""
        blocks = []
        for event in events:
            evt_start = self._parse_iso_datetime(event["start_date"])
            evt_end = self._parse_iso_datetime(event["end_date"])

            if event.get("allday_event"):
                evt_start = evt_start.replace(hour=0, minute=0, second=0)
                evt_end = evt_end.replace(hour=0, minute=0, second=0)
                if evt_end == evt_start:
                    evt_end += timedelta(days=1)

            blocks.append((evt_start, evt_end))

        blocks.sort(key=lambda b: b[0])

        merged = []
        for start, end in blocks:
            if merged and start <= merged[-1][1]:
                merged[-1] = (merged[-1][0], max(merged[-1][1], end))
            else:
                merged.append((start, end))

        return merged

    def get_availability(
        self,
        calendar_names: list[str],
        start_date: str,
        end_date: str,
    ) -> list[dict[str, Any]]:
        """Get free time slots across one or more calendars.

        Queries events from all specified calendars, merges overlapping busy
        periods, and returns the gaps (free slots) within the date range.

        Args:
            calendar_names: List of calendar names to check
            start_date: Start of range in ISO 8601 format
            end_date: End of range in ISO 8601 format

        Returns:
            List of dicts with 'start_date', 'end_date', 'duration_minutes' keys
            representing free time slots.

        Raises:
            ValueError: If date format is invalid, calendar not found, or no calendars provided
            PermissionError: If EventKit calendar access is denied
        """
        if not calendar_names:
            raise ValueError("At least one calendar name must be provided")

        range_start = self._parse_iso_datetime(start_date)
        range_end = self._parse_iso_datetime(end_date)

        all_events = []
        for cal_name in calendar_names:
            all_events.extend(self.get_events(cal_name, start_date, end_date))

        merged = self._build_busy_blocks(all_events)

        free_slots = []
        cursor = range_start

        for busy_start, busy_end in merged:
            busy_start = max(busy_start, range_start)
            busy_end = min(busy_end, range_end)

            if cursor < busy_start:
                duration = int((busy_start - cursor).total_seconds() / 60)
                free_slots.append({
                    "start_date": cursor.isoformat(),
                    "end_date": busy_start.isoformat(),
                    "duration_minutes": duration,
                })
            cursor = max(cursor, busy_end)

        if cursor < range_end:
            duration = int((range_end - cursor).total_seconds() / 60)
            free_slots.append({
                "start_date": cursor.isoformat(),
                "end_date": range_end.isoformat(),
                "duration_minutes": duration,
            })

        return free_slots

    def get_calendars(self) -> list[dict[str, Any]]:
        """Get all calendars from Apple Calendar.

        Uses EventKit via Swift helper for fast native access.

        Returns:
            List of calendar dicts with keys: name, writable, description, color.
            Calendars are identified by name. Duplicate names may exist across accounts.

        Raises:
            PermissionError: If EventKit calendar access is denied
        """
        return self._run_swift_helper_json("get_calendars", [])

    def create_calendar(self, name: str) -> dict[str, str]:
        """Create a new calendar in Apple Calendar.

        Args:
            name: Name for the new calendar

        Returns:
            Dict with 'name' key of the created calendar

        Raises:
            subprocess.CalledProcessError: If AppleScript execution fails
        """
        escaped = self._escape_applescript_string(name)
        run_applescript(
            f'tell application "Calendar" to make new calendar with properties {{name:"{escaped}"}}'
        )
        return {"name": name}

    def delete_calendar(self, name: str) -> dict[str, str]:
        """Delete a calendar from Apple Calendar.

        Args:
            name: Name of the calendar to delete

        Returns:
            Dict with 'name' key of the deleted calendar

        Raises:
            CalendarSafetyError: If safety checks block the target calendar
            ValueError: If the calendar doesn't exist
            subprocess.CalledProcessError: If AppleScript execution fails
        """
        self._verify_calendar_safety(name)
        escaped = self._escape_applescript_string(name)
        try:
            run_applescript(f'tell application "Calendar" to delete calendar "{escaped}"')
        except subprocess.CalledProcessError as e:
            raise ValueError(f"Calendar '{name}' not found or could not be deleted") from e
        return {"name": name}
