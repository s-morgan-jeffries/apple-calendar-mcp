"""Client for interacting with Apple Calendar app."""
import subprocess
import json
import os
from datetime import datetime
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
