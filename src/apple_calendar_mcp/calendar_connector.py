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


# AppleScript helper functions for JSON escaping
#
# NOTE: These helpers will be embedded in every AppleScript block that returns JSON.
# AppleScript does not support imports or modules, so each block must be
# completely self-contained. This duplication is intentional.
#
# DO NOT attempt to refactor this duplication — it will break AppleScript execution.
APPLESCRIPT_JSON_HELPERS = '''
-- Helper to escape JSON strings
on escapeJSON(txt)
    set txt to my replaceText(txt, "\\\\", "\\\\\\\\")
    set txt to my replaceText(txt, "\\"", "\\\\\\"")
    set txt to my replaceText(txt, linefeed, "\\\\n")
    set txt to my replaceText(txt, return, "\\\\r")
    set txt to my replaceText(txt, tab, "\\\\t")
    return txt
end escapeJSON

-- Helper to replace text
on replaceText(sourceText, oldText, newText)
    set AppleScript's text item delimiters to oldText
    set textItems to text items of sourceText
    set AppleScript's text item delimiters to newText
    set resultText to textItems as text
    set AppleScript's text item delimiters to ""
    return resultText
end replaceText
'''


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

        Returns:
            The UID of the created event

        Raises:
            CalendarSafetyError: If safety checks block the target calendar
            ValueError: If date format is invalid
            subprocess.CalledProcessError: If AppleScript execution fails
        """
        self._verify_calendar_safety(calendar_name)

        # Convert dates (validates format)
        as_start = self._iso_to_applescript_date(start_date)
        as_end = self._iso_to_applescript_date(end_date)

        # Escape user-provided strings
        cal_escaped = self._escape_applescript_string(calendar_name)
        summary_escaped = self._escape_applescript_string(summary)

        # Build allday property
        allday_str = "true" if allday_event else "false"

        # Build optional property setters
        optional_lines = []
        if location:
            loc_escaped = self._escape_applescript_string(location)
            optional_lines.append(
                f'        set location of newEvent to "{loc_escaped}"'
            )
        if description:
            desc_escaped = self._escape_applescript_string(description)
            optional_lines.append(
                f'        set description of newEvent to "{desc_escaped}"'
            )
        if url:
            url_escaped = self._escape_applescript_string(url)
            optional_lines.append(
                f'        set url of newEvent to "{url_escaped}"'
            )

        optional_block = "\n".join(optional_lines)
        if optional_block:
            optional_block = "\n" + optional_block

        script = f'''tell application "Calendar"
    tell calendar "{cal_escaped}"
        set newEvent to make new event at end of events with properties {{summary:"{summary_escaped}", start date:date "{as_start}", end date:date "{as_end}", allday event:{allday_str}}}
{optional_block}
        return uid of newEvent
    end tell
end tell'''

        return run_applescript(script).strip()

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

        result = run_swift_helper(
            "get_events",
            ["--calendar", calendar_name, "--start", start_date, "--end", end_date],
        )
        parsed = json.loads(result)

        # Handle error responses from Swift helper
        if isinstance(parsed, dict) and "error" in parsed:
            if parsed["error"] == "calendar_access_denied":
                raise PermissionError(parsed["message"])
            else:
                raise ValueError(parsed["message"])

        return parsed

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
    ) -> dict[str, Any]:
        """Update an existing event's properties by UID.

        Only provided fields are updated; omitted fields (None) are left unchanged.
        Pass an empty string to clear a text field.

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

        Returns:
            Dict with 'uid' and 'updated_fields' keys

        Raises:
            CalendarSafetyError: If safety checks block the target calendar
            ValueError: If no fields provided or date format is invalid
            subprocess.CalledProcessError: If AppleScript execution fails
        """
        self._verify_calendar_safety(calendar_name)

        # Build set lines and track updated fields
        set_lines = []
        updated_fields = []

        # String fields: property name in AppleScript → (field_name, value)
        string_fields = [
            ("summary", "summary", summary),
            ("location", "location", location),
            ("description", "description", description),
            ("url", "url", url),
        ]
        for as_prop, field_name, value in string_fields:
            if value is not None:
                escaped = self._escape_applescript_string(value)
                set_lines.append(f'        set {as_prop} of evt to "{escaped}"')
                updated_fields.append(field_name)

        # Date fields: handle ordering to avoid start > end constraint
        if start_date is not None and end_date is not None:
            as_start = self._iso_to_applescript_date(start_date)
            as_end = self._iso_to_applescript_date(end_date)
            set_lines.append('        set end date of evt to date "December 31, 2099 11:59:59 PM"')
            set_lines.append(f'        set start date of evt to date "{as_start}"')
            set_lines.append(f'        set end date of evt to date "{as_end}"')
            updated_fields.extend(["start_date", "end_date"])
        elif start_date is not None:
            as_date = self._iso_to_applescript_date(start_date)
            set_lines.append(f'        set start date of evt to date "{as_date}"')
            updated_fields.append("start_date")
        elif end_date is not None:
            as_date = self._iso_to_applescript_date(end_date)
            set_lines.append(f'        set end date of evt to date "{as_date}"')
            updated_fields.append("end_date")

        if allday_event is not None:
            allday_str = "true" if allday_event else "false"
            set_lines.append(f"        set allday event of evt to {allday_str}")
            updated_fields.append("allday_event")

        if not updated_fields:
            raise ValueError("At least one field must be provided to update")

        cal_escaped = self._escape_applescript_string(calendar_name)
        uid_escaped = self._escape_applescript_string(event_uid)
        set_block = "\n".join(set_lines)

        script = f'''tell application "Calendar"
    tell calendar "{cal_escaped}"
        set matchingEvents to (every event whose uid is "{uid_escaped}")
        if (count of matchingEvents) is 0 then
            error "Event not found: {uid_escaped}"
        end if
        set evt to item 1 of matchingEvents
{set_block}
        return uid of evt
    end tell
end tell'''

        run_applescript(script)
        return {"uid": event_uid, "updated_fields": updated_fields}

    def delete_events(
        self,
        calendar_name: str,
        event_uids: str | list[str],
    ) -> dict[str, Any]:
        """Delete one or more events by UID.

        Args:
            calendar_name: Name of the calendar containing the events
            event_uids: Single UID string or list of UIDs to delete

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

        cal_escaped = self._escape_applescript_string(calendar_name)
        deleted_uids = []
        not_found_uids = []

        for uid in uids:
            uid_escaped = self._escape_applescript_string(uid)
            script = f'''tell application "Calendar"
    tell calendar "{cal_escaped}"
        set matchingEvents to (every event whose uid is "{uid_escaped}")
        if (count of matchingEvents) is 0 then
            error "Event not found: {uid_escaped}"
        end if
        repeat with evt in matchingEvents
            delete evt
        end repeat
    end tell
end tell'''
            try:
                run_applescript(script)
                deleted_uids.append(uid)
            except subprocess.CalledProcessError:
                not_found_uids.append(uid)

        return {"deleted_uids": deleted_uids, "not_found_uids": not_found_uids}

    def _parse_iso_datetime(self, date_str: str) -> datetime:
        """Parse an ISO 8601 date string to a datetime object.

        Raises:
            ValueError: If the date format is invalid.
        """
        try:
            if "T" in date_str:
                return datetime.fromisoformat(date_str.replace("Z", "+00:00")).replace(tzinfo=None)
            else:
                return datetime.fromisoformat(date_str + "T00:00:00")
        except ValueError as e:
            raise ValueError(
                f"Invalid date format '{date_str}'. "
                "Expected ISO 8601 format like '2026-03-15' or '2026-03-15T14:30:00'"
            ) from e

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

        # Collect all events across calendars
        all_events = []
        for cal_name in calendar_names:
            events = self.get_events(cal_name, start_date, end_date)
            all_events.extend(events)

        # Build busy blocks from events
        busy_blocks = []
        for event in all_events:
            evt_start = self._parse_iso_datetime(event["start_date"])
            evt_end = self._parse_iso_datetime(event["end_date"])

            # All-day events block the full day(s)
            if event.get("allday_event"):
                evt_start = evt_start.replace(hour=0, minute=0, second=0)
                evt_end = evt_end.replace(hour=0, minute=0, second=0)
                if evt_end == evt_start:
                    evt_end += timedelta(days=1)

            busy_blocks.append((evt_start, evt_end))

        # Sort by start time
        busy_blocks.sort(key=lambda b: b[0])

        # Merge overlapping/adjacent blocks
        merged = []
        for start, end in busy_blocks:
            if merged and start <= merged[-1][1]:
                merged[-1] = (merged[-1][0], max(merged[-1][1], end))
            else:
                merged.append((start, end))

        # Compute free slots (gaps between busy blocks within the range)
        free_slots = []
        cursor = range_start

        for busy_start, busy_end in merged:
            # Clamp to range
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

        # Gap after last busy block
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

        Returns:
            List of calendar dicts with keys: name, writable, description, color.
            Note: Calendar UIDs are not accessible via AppleScript (AppleEvent error -10000).
            Calendars are identified by name. Duplicate names may exist across accounts.
        """
        script = f'''
{APPLESCRIPT_JSON_HELPERS}

tell application "Calendar"
    set calNames to name of every calendar
    set calWritable to writable of every calendar
    set calDescs to description of every calendar
    set calColors to color of every calendar
    set calCount to count of calNames
    set jsonResult to "["
    repeat with i from 1 to calCount
        set calName to item i of calNames
        set calWrite to item i of calWritable
        set calDesc to item i of calDescs
        -- Colors are returned as list of {{R, G, B}} per calendar (16-bit values)
        set calColor to item i of calColors
        set colorR to item 1 of calColor
        set colorG to item 2 of calColor
        set colorB to item 3 of calColor
        -- Convert 16-bit RGB to hex
        set hexR to my toHex(colorR div 256)
        set hexG to my toHex(colorG div 256)
        set hexB to my toHex(colorB div 256)
        set hexColor to "#" & hexR & hexG & hexB

        -- Handle missing description
        if calDesc is missing value then
            set calDesc to ""
        end if

        -- Handle boolean writable
        if calWrite then
            set writeStr to "true"
        else
            set writeStr to "false"
        end if

        set jsonItem to "{{\\"name\\":\\"" & my escapeJSON(calName) & "\\",\\"writable\\":" & writeStr & ",\\"description\\":\\"" & my escapeJSON(calDesc) & "\\",\\"color\\":\\"" & hexColor & "\\"}}"
        if i > 1 then
            set jsonResult to jsonResult & ","
        end if
        set jsonResult to jsonResult & jsonItem
    end repeat
    set jsonResult to jsonResult & "]"
    return jsonResult
end tell

on toHex(val)
    set hexChars to "0123456789ABCDEF"
    if val < 0 then set val to 0
    if val > 255 then set val to 255
    set hi to (val div 16) + 1
    set lo to (val mod 16) + 1
    return (character hi of hexChars) & (character lo of hexChars)
end toHex
'''
        result = run_applescript(script)
        return json.loads(result)
