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


def run_swift_helper(
    script_name: str,
    args: list[str],
    timeout: int = 30,
    stdin_data: Optional[str] = None,
) -> str:
    """Execute a Swift helper script and return the result.

    Args:
        script_name: Name of the Swift script (without .swift extension)
        args: Command-line arguments to pass to the script
        timeout: Maximum seconds to wait (default: 30)
        stdin_data: Optional data to pipe to the script's stdin

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
        input=stdin_data,
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

    def _run_swift_helper_json(
        self, script_name: str, args: list[str], stdin_data: Optional[str] = None
    ) -> dict:
        """Run a Swift helper and parse JSON response, raising on errors."""
        try:
            result = run_swift_helper(script_name, args, stdin_data=stdin_data)
        except subprocess.CalledProcessError as e:
            # Swift helpers exit(1) on error but still write JSON to stdout
            result = (e.stdout or "").strip()
            if not result:
                raise RuntimeError(f"Swift helper '{script_name}' failed with no output") from e
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

    def create_events(
        self,
        calendar_name: str = "",
        events: list[dict[str, Any]] | None = None,
    ) -> dict[str, Any]:
        """Create one or more events in a calendar.

        Args:
            calendar_name: Name of the target calendar. If empty, uses the system
                          default calendar.
            events: List of event dicts, each with keys: summary, start, end,
                    and optional: location, notes, url, allday, recurrence,
                    alerts (list of int), availability, timezone

        Returns:
            Dict with 'created' (list of {uid, summary}) and 'errors' (list of {index, summary, error})
        """
        if calendar_name:
            self._verify_calendar_safety(calendar_name)

        if not events:
            raise ValueError("At least one event must be provided")

        stdin_data = json.dumps(events)
        return self._run_swift_helper_json(
            "create_events", ["--calendar", calendar_name], stdin_data=stdin_data
        )

    def update_events(
        self,
        calendar_name: str,
        updates: list[dict[str, Any]],
    ) -> dict[str, Any]:
        """Update one or more events in a single batch operation.

        Args:
            calendar_name: Name of the calendar containing the events
            updates: List of update dicts, each with 'uid' (required) and optional fields
                     to update: summary, start, end, location, notes, url, allday,
                     alerts, availability, timezone, recurrence, clear_location,
                     clear_notes, clear_url, clear_alerts, clear_recurrence.
                     For recurring events: occurrence_date (ISO 8601) to target a specific
                     occurrence, span ("this_event" or "future_events", default "this_event").

        Returns:
            Dict with 'updated' (list of {uid, summary, updated_fields}) and 'errors'.
            When rescheduling a recurring event occurrence (changing dates with
            span="this_event"), a new standalone event is created — the returned UID
            may differ, and 'rescheduled': true is included.
        """
        self._verify_calendar_safety(calendar_name)

        if not updates:
            raise ValueError("At least one update must be provided")

        stdin_data = json.dumps(updates)
        return self._run_swift_helper_json(
            "update_events", ["--calendar", calendar_name], stdin_data=stdin_data
        )

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
            allday_event, location, notes, url, status, calendar_name.

        Raises:
            ValueError: If date format is invalid or calendar not found
            PermissionError: If EventKit calendar access is denied
        """
        self._validate_date(start_date)
        self._validate_date(end_date)

        args = ["--calendar", calendar_name, "--start", start_date, "--end", end_date]
        events = self._run_swift_helper_json("get_events", args)
        for event in events:
            if event.get("allday_event"):
                event["end_date"] = self._allday_end_from_eventkit(event["end_date"])
        return events

    def search_events(
        self,
        query: str,
        calendar_name: Optional[str] = None,
        start_date: Optional[str] = None,
        end_date: Optional[str] = None,
    ) -> list[dict[str, Any]]:
        """Search events by text across one or all calendars.

        Searches event summaries, notes, and locations with
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
                    for event in events:
                        if event.get("allday_event"):
                            event["end_date"] = self._allday_end_from_eventkit(event["end_date"])
                    all_results.extend(events)
            except ValueError:
                continue  # skip calendars that error (e.g., not found)

        return all_results

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

    def _allday_end_from_eventkit(self, end_date: str) -> str:
        """Extract date portion from EventKit all-day end_date.

        EventKit returns all-day end dates as the last day at 23:59:59
        (e.g., "2027-08-01T23:59:59" for a single-day event on Aug 1).
        This extracts just the date portion for a clean inclusive end date.
        """
        dt = self._parse_iso_datetime(end_date)
        return dt.strftime("%Y-%m-%d")

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
                evt_end += timedelta(days=1)  # Convert inclusive to exclusive for calculations

            blocks.append((evt_start, evt_end))

        blocks.sort(key=lambda b: b[0])

        merged = []
        for start, end in blocks:
            if merged and start <= merged[-1][1]:
                merged[-1] = (merged[-1][0], max(merged[-1][1], end))
            else:
                merged.append((start, end))

        return merged

    @staticmethod
    def _parse_time_string(time_str: str) -> tuple[int, int]:
        """Parse 'HH:MM' time string to (hour, minute) tuple."""
        parts = time_str.split(":")
        if len(parts) != 2:
            raise ValueError(
                f"Invalid time format '{time_str}'. Expected 'HH:MM' (e.g., '09:00')"
            )
        try:
            hour, minute = int(parts[0]), int(parts[1])
        except ValueError:
            raise ValueError(
                f"Invalid time format '{time_str}'. Expected 'HH:MM' (e.g., '09:00')"
            )
        if not (0 <= hour <= 23 and 0 <= minute <= 59):
            raise ValueError(
                f"Invalid time '{time_str}'. Hour must be 0-23, minute must be 0-59"
            )
        return (hour, minute)

    def _clip_to_working_hours(
        self,
        slots: list[dict[str, Any]],
        wh_start: tuple[int, int],
        wh_end: tuple[int, int],
    ) -> list[dict[str, Any]]:
        """Clip free slots to working hours, splitting multi-day slots per day."""
        clipped: list[dict[str, Any]] = []
        for slot in slots:
            slot_start = self._parse_iso_datetime(slot["start_date"])
            slot_end = self._parse_iso_datetime(slot["end_date"])

            current_day = slot_start.date()
            end_day = slot_end.date()
            if slot_end.time() == datetime.min.time() and end_day > current_day:
                end_day -= timedelta(days=1)

            while current_day <= end_day:
                wh_begin = datetime(
                    current_day.year, current_day.month, current_day.day,
                    wh_start[0], wh_start[1],
                )
                wh_finish = datetime(
                    current_day.year, current_day.month, current_day.day,
                    wh_end[0], wh_end[1],
                )
                clipped_start = max(slot_start, wh_begin)
                clipped_end = min(slot_end, wh_finish)

                if clipped_start < clipped_end:
                    duration = int((clipped_end - clipped_start).total_seconds() / 60)
                    clipped.append({
                        "start_date": clipped_start.isoformat(),
                        "end_date": clipped_end.isoformat(),
                        "duration_minutes": duration,
                    })
                current_day += timedelta(days=1)

        return clipped

    def get_availability(
        self,
        calendar_names: list[str],
        start_date: str,
        end_date: str,
        min_duration_minutes: int | None = None,
        working_hours_start: str | None = None,
        working_hours_end: str | None = None,
    ) -> list[dict[str, Any]]:
        """Get free time slots across one or more calendars.

        Queries events from all specified calendars, merges overlapping busy
        periods, and returns the gaps (free slots) within the date range.

        Args:
            calendar_names: List of calendar names to check
            start_date: Start of range in ISO 8601 format
            end_date: End of range in ISO 8601 format
            min_duration_minutes: Only return slots of at least this many minutes
            working_hours_start: Start of working hours as 'HH:MM' (e.g., '09:00')
            working_hours_end: End of working hours as 'HH:MM' (e.g., '17:00')

        Returns:
            List of dicts with 'start_date', 'end_date', 'duration_minutes' keys
            representing free time slots.

        Raises:
            ValueError: If date format is invalid, calendar not found, or no calendars provided
            PermissionError: If EventKit calendar access is denied
        """
        if min_duration_minutes is not None and min_duration_minutes < 1:
            raise ValueError("min_duration_minutes must be a positive integer")

        wh_start = None
        wh_end = None
        if working_hours_start is not None or working_hours_end is not None:
            if working_hours_start is None or working_hours_end is None:
                raise ValueError(
                    "Both working_hours_start and working_hours_end must be provided together"
                )
            wh_start = self._parse_time_string(working_hours_start)
            wh_end = self._parse_time_string(working_hours_end)
            if wh_start >= wh_end:
                raise ValueError(
                    "working_hours_start must be before working_hours_end"
                )

        if not calendar_names:
            raise ValueError("At least one calendar name must be provided")

        range_start = self._parse_iso_datetime(start_date)
        range_end = self._parse_iso_datetime(end_date)

        all_events = []
        for cal_name in calendar_names:
            all_events.extend(self.get_events(cal_name, start_date, end_date))

        # Only busy/tentative events block availability — free events are excluded
        busy_events = [e for e in all_events if e.get("availability", "busy") != "free"]

        merged = self._build_busy_blocks(busy_events)

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

        if wh_start is not None and wh_end is not None:
            free_slots = self._clip_to_working_hours(free_slots, wh_start, wh_end)

        if min_duration_minutes is not None:
            free_slots = [
                s for s in free_slots if s["duration_minutes"] >= min_duration_minutes
            ]

        return free_slots

    def get_conflicts(
        self,
        calendar_names: list[str],
        start_date: str,
        end_date: str,
    ) -> list[dict[str, Any]]:
        """Detect overlapping events across one or more calendars.

        Fetches events from all specified calendars, filters out events marked
        as "free", and returns pairs of events that overlap in time.

        Args:
            calendar_names: List of calendar names to check
            start_date: Start of range in ISO 8601 format
            end_date: End of range in ISO 8601 format

        Returns:
            List of conflict dicts, each with 'event_a', 'event_b',
            'overlap_start', 'overlap_end', and 'overlap_minutes' keys.

        Raises:
            ValueError: If date format is invalid, calendar not found, or no calendars provided
            PermissionError: If EventKit calendar access is denied
        """
        if not calendar_names:
            raise ValueError("At least one calendar name must be provided")

        all_events = []
        for cal_name in calendar_names:
            all_events.extend(self.get_events(cal_name, start_date, end_date))

        # Filter out free events — only busy/tentative can conflict
        busy_events = [
            e for e in all_events
            if e.get("availability", "busy") != "free"
        ]

        # Parse dates and sort
        parsed = []
        for event in busy_events:
            evt_start = self._parse_iso_datetime(event["start_date"])
            evt_end = self._parse_iso_datetime(event["end_date"])
            if event.get("allday_event"):
                evt_start = evt_start.replace(hour=0, minute=0, second=0)
                evt_end = evt_end.replace(hour=0, minute=0, second=0)
                evt_end += timedelta(days=1)  # Convert inclusive to exclusive for calculations
            parsed.append((evt_start, evt_end, event))
        parsed.sort(key=lambda x: x[0])

        # Find all overlapping pairs
        conflicts = []
        for i in range(len(parsed)):
            for j in range(i + 1, len(parsed)):
                start_a, end_a, event_a = parsed[i]
                start_b, end_b, event_b = parsed[j]
                if start_b >= end_a:
                    break  # No more overlaps possible for event i
                overlap_start = max(start_a, start_b)
                overlap_end = min(end_a, end_b)
                overlap_minutes = int((overlap_end - overlap_start).total_seconds() / 60)
                if overlap_minutes > 0:
                    conflicts.append({
                        "event_a": {
                            "uid": event_a["uid"],
                            "summary": event_a["summary"],
                            "start_date": event_a["start_date"],
                            "end_date": event_a["end_date"],
                            "calendar_name": event_a["calendar_name"],
                        },
                        "event_b": {
                            "uid": event_b["uid"],
                            "summary": event_b["summary"],
                            "start_date": event_b["start_date"],
                            "end_date": event_b["end_date"],
                            "calendar_name": event_b["calendar_name"],
                        },
                        "overlap_start": overlap_start.isoformat(),
                        "overlap_end": overlap_end.isoformat(),
                        "overlap_minutes": overlap_minutes,
                    })

        return conflicts

    def get_calendars(self) -> list[dict[str, Any]]:
        """Get all calendars from Apple Calendar.

        Uses EventKit via Swift helper for fast native access.

        Returns:
            List of calendar dicts with keys: name, writable, description, color, type, source.
            Calendars are identified by name. Duplicate names may exist across accounts.
            Use source (account name) to disambiguate.

        Raises:
            PermissionError: If EventKit calendar access is denied
        """
        return self._run_swift_helper_json("get_calendars", [])

    def create_calendar(self, name: str) -> dict[str, str]:
        """Create a new calendar in Apple Calendar.

        Uses EventKit via Swift helper for native calendar creation.

        Args:
            name: Name for the new calendar

        Returns:
            Dict with 'name' and optionally 'source' keys of the created calendar

        Raises:
            RuntimeError: If Swift helper execution fails
            PermissionError: If EventKit calendar access is denied
        """
        return self._run_swift_helper_json("create_calendar", ["--name", name])

    def delete_calendar(self, name: str) -> dict[str, str]:
        """Delete a calendar from Apple Calendar.

        Uses EventKit via Swift helper for native calendar deletion.

        Args:
            name: Name of the calendar to delete

        Returns:
            Dict with 'name' key of the deleted calendar

        Raises:
            CalendarSafetyError: If safety checks block the target calendar
            ValueError: If the calendar doesn't exist
            PermissionError: If EventKit calendar access is denied
        """
        self._verify_calendar_safety(name)
        return self._run_swift_helper_json("delete_calendar", ["--name", name])
