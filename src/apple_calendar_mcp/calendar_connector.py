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
    MAX_BATCH_SIZE = 50

    def __init__(self, enable_safety_checks: bool = True):
        self.enable_safety_checks = enable_safety_checks

    @staticmethod
    def _validate_cli_arg(value: str, name: str) -> None:
        """Reject values starting with '--' to prevent CLI arg confusion."""
        if value.startswith("--"):
            raise ValueError(f"{name} must not start with '--': {value!r}")

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
                "ambiguous_calendar": ValueError,
                "event_not_found": ValueError,
            }
            exc_type = error_map.get(parsed["error"], RuntimeError)
            raise exc_type(parsed["message"])
        return parsed

    def create_events(
        self,
        calendar_name: str = "",
        events: list[dict[str, Any]] | None = None,
        calendar_source: str = "",
    ) -> dict[str, Any]:
        """Create one or more events in a calendar.

        Args:
            calendar_name: Name of the target calendar. If empty, uses the system
                          default calendar.
            events: List of event dicts, each with keys: summary, start, end,
                    and optional: location, notes, url, allday, recurrence,
                    alerts (list of int), availability, timezone
            calendar_source: Source/account name to disambiguate calendars with
                           the same name (e.g., 'iCloud', 'Google').

        Returns:
            Dict with 'created' (list of {uid, summary}) and 'errors' (list of {index, summary, error})
        """
        if self.enable_safety_checks and not calendar_name:
            raise CalendarSafetyError(
                "calendar_name is required when safety checks are enabled "
                "(empty name would target the default calendar)"
            )
        if calendar_name:
            self._verify_calendar_safety(calendar_name)

        if not events:
            raise ValueError("At least one event must be provided")
        if len(events) > self.MAX_BATCH_SIZE:
            raise ValueError(
                f"Batch size {len(events)} exceeds limit of {self.MAX_BATCH_SIZE}. "
                f"Split into multiple calls."
            )

        if calendar_name:
            self._validate_cli_arg(calendar_name, "calendar_name")
        if calendar_source:
            self._validate_cli_arg(calendar_source, "calendar_source")

        args = ["--calendar", calendar_name]
        if calendar_source:
            args += ["--source", calendar_source]

        stdin_data = json.dumps(events)
        return self._run_swift_helper_json(
            "create_events", args, stdin_data=stdin_data
        )

    def update_events(
        self,
        calendar_name: str,
        updates: list[dict[str, Any]],
        calendar_source: str = "",
    ) -> dict[str, Any]:
        """Update one or more events in a single batch operation.

        Args:
            calendar_name: Name of the calendar containing the events
            updates: List of update dicts, each with 'uid' (required) and optional fields
                     to update: summary, start, end, location, notes, url, allday,
                     alerts, availability, timezone, recurrence.
                     To clear a field, pass an empty value (e.g., location="", alerts=[]).
                     For recurring events: occurrence_date (ISO 8601) to target a specific
                     occurrence, span ("this_event" or "future_events", default "this_event").
            calendar_source: Source/account name to disambiguate calendars with
                           the same name (e.g., 'iCloud', 'Google').

        Returns:
            Dict with 'updated' (list of {uid, summary, updated_fields}) and 'errors'.
            When rescheduling a recurring event occurrence (changing dates with
            span="this_event"), a new standalone event is created — the returned UID
            may differ, and 'rescheduled': true is included.
        """
        self._verify_calendar_safety(calendar_name)
        self._validate_cli_arg(calendar_name, "calendar_name")
        if calendar_source:
            self._validate_cli_arg(calendar_source, "calendar_source")

        if not updates:
            raise ValueError("At least one update must be provided")
        if len(updates) > self.MAX_BATCH_SIZE:
            raise ValueError(
                f"Batch size {len(updates)} exceeds limit of {self.MAX_BATCH_SIZE}. "
                f"Split into multiple calls."
            )

        args = ["--calendar", calendar_name]
        if calendar_source:
            args += ["--source", calendar_source]

        stdin_data = json.dumps(updates)
        return self._run_swift_helper_json(
            "update_events", args, stdin_data=stdin_data
        )

    def _normalize_calendar_names(
        self,
        calendar_names: list[str] | str | None,
        calendar_name: str | None = None,
    ) -> list[str]:
        """Normalize calendar_names parameter to a list of strings.

        Handles backward-compat calendar_name alias and str/None/list inputs.
        """
        if calendar_name is not None and calendar_names is None:
            calendar_names = [calendar_name] if calendar_name else []

        if calendar_names is None:
            calendar_names = []
        elif isinstance(calendar_names, str):
            calendar_names = [calendar_names] if calendar_names else []

        return calendar_names

    def _apply_search_date_defaults(
        self,
        start_date: Optional[str],
        end_date: Optional[str],
    ) -> tuple[str, str]:
        """Apply default date range for search: 30 days ago to 180 days ahead."""
        if not start_date:
            start_date = (datetime.now() - timedelta(days=30)).strftime("%Y-%m-%dT00:00:00")
        if not end_date:
            end_date = (datetime.now() + timedelta(days=180)).strftime("%Y-%m-%dT00:00:00")
        return start_date, end_date

    def _process_allday_events(self, events: list[dict]) -> list[dict]:
        """Adjust end dates for all-day events to inclusive date-only format."""
        for event in events:
            if event.get("allday_event"):
                event["end_date"] = self._allday_end_from_eventkit(event["end_date"])
        return events

    def _validate_working_hours(
        self,
        wh_start_str: str | None,
        wh_end_str: str | None,
    ) -> tuple[tuple[int, int], tuple[int, int]] | None:
        """Validate and parse working hours parameters.

        Returns:
            Parsed (start, end) tuple pair, or None if not provided.

        Raises:
            ValueError: If only one bound is provided or start >= end.
        """
        if wh_start_str is None and wh_end_str is None:
            return None
        if wh_start_str is None or wh_end_str is None:
            raise ValueError(
                "Both working_hours_start and working_hours_end must be provided together"
            )
        wh_start = self._parse_time_string(wh_start_str)
        wh_end = self._parse_time_string(wh_end_str)
        if wh_start >= wh_end:
            raise ValueError(
                "working_hours_start must be before working_hours_end"
            )
        return (wh_start, wh_end)

    def _calculate_free_slots(
        self,
        merged_busy: list[tuple[datetime, datetime]],
        range_start: datetime,
        range_end: datetime,
    ) -> list[dict[str, Any]]:
        """Compute free time slots from gaps between merged busy blocks."""
        free_slots: list[dict[str, Any]] = []
        cursor = range_start

        for busy_start, busy_end in merged_busy:
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

    def _apply_availability_filters(
        self,
        slots: list[dict[str, Any]],
        wh: tuple[tuple[int, int], tuple[int, int]] | None,
        min_duration: int | None,
    ) -> list[dict[str, Any]]:
        """Apply working-hours clipping and min-duration filtering to slots."""
        if wh is not None:
            slots = self._clip_to_working_hours(slots, wh[0], wh[1])
        if min_duration is not None:
            slots = [s for s in slots if s["duration_minutes"] >= min_duration]
        return slots

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
        calendar_names: list[str] | str | None = None,
        start_date: str = "",
        end_date: str = "",
        *,
        calendar_name: str | None = None,  # backward compat alias
    ) -> list[dict[str, Any]]:
        """Get events from one or more calendars within a date range.

        Uses EventKit via Swift helper for fast native date-range queries.

        Args:
            calendar_names: Calendar name(s) to query. Accepts a list of names,
                a single name string, or None/empty list to query all calendars.
            start_date: Start of date range in ISO 8601 format
            end_date: End of date range in ISO 8601 format

        Returns:
            List of event dicts with keys: uid, summary, start_date, end_date,
            allday_event, location, notes, url, status, calendar_name.

        Raises:
            ValueError: If date format is invalid or calendar not found
            PermissionError: If EventKit calendar access is denied
        """
        calendar_names = self._normalize_calendar_names(calendar_names, calendar_name)
        for name in calendar_names:
            self._validate_cli_arg(name, "calendar_name")

        self._validate_date(start_date)
        self._validate_date(end_date)

        args = []
        for name in calendar_names:
            args += ["--calendar", name]
        args += ["--start", start_date, "--end", end_date]
        events = self._run_swift_helper_json("get_events", args)
        return self._process_allday_events(events)

    def search_events(
        self,
        query: str,
        calendar_names: list[str] | str | None = None,
        start_date: Optional[str] = None,
        end_date: Optional[str] = None,
        *,
        calendar_name: str | None = None,  # backward compat alias
    ) -> list[dict[str, Any]]:
        """Search events by text across one or more calendars.

        Searches event summaries, notes, and locations with
        case-insensitive matching.

        Args:
            query: Text to search for
            calendar_names: Calendar name(s) to search. Accepts a list of names,
                a single name string, or None/empty list to search all calendars.
            start_date: Start of date range (optional — defaults to 1 month ago)
            end_date: End of date range (optional — defaults to 6 months from now)

        Returns:
            List of matching event dicts.
        """
        calendar_names = self._normalize_calendar_names(calendar_names, calendar_name)
        for name in calendar_names:
            self._validate_cli_arg(name, "calendar_name")
        start_date, end_date = self._apply_search_date_defaults(start_date, end_date)

        self._validate_date(start_date)
        self._validate_date(end_date)

        self._validate_cli_arg(query, "query")

        args = []
        for name in calendar_names:
            args += ["--calendar", name]
        args += ["--start", start_date, "--end", end_date, "--query", query]
        events = self._run_swift_helper_json("get_events", args)
        if isinstance(events, list):
            self._process_allday_events(events)
        return events if isinstance(events, list) else []

    def delete_events(
        self,
        calendar_name: str,
        event_uids: str | list[str],
        span: str = "this_event",
        occurrence_date: Optional[str] = None,
        calendar_source: str = "",
    ) -> dict[str, Any]:
        """Delete one or more events by UID.

        Args:
            calendar_name: Name of the calendar containing the events
            event_uids: Single UID string or list of UIDs to delete
            span: "this_event" to delete one occurrence, "future_events" to delete series from this point (default: "this_event")
            occurrence_date: For recurring events, the date of the specific occurrence to delete (optional)
            calendar_source: Source/account name to disambiguate calendars with
                           the same name (e.g., 'iCloud', 'Google').

        Returns:
            Dict with 'deleted_uids' and 'not_found_uids' keys

        Raises:
            CalendarSafetyError: If safety checks block the target calendar
            ValueError: If event_uids is empty
        """
        self._verify_calendar_safety(calendar_name)
        self._validate_cli_arg(calendar_name, "calendar_name")
        if calendar_source:
            self._validate_cli_arg(calendar_source, "calendar_source")

        uids = [event_uids] if isinstance(event_uids, str) else event_uids
        if not uids:
            raise ValueError("At least one event UID must be provided")
        for uid in uids:
            self._validate_cli_arg(uid, "event_uid")
        if len(uids) > self.MAX_BATCH_SIZE:
            raise ValueError(
                f"Batch size {len(uids)} exceeds limit of {self.MAX_BATCH_SIZE}. "
                f"Split into multiple calls."
            )

        args = ["--calendar", calendar_name]
        if calendar_source:
            args += ["--source", calendar_source]
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

        wh = self._validate_working_hours(working_hours_start, working_hours_end)

        range_start = self._parse_iso_datetime(start_date)
        range_end = self._parse_iso_datetime(end_date)

        all_events = self.get_events(calendar_names, start_date, end_date)

        # Only busy/tentative events block availability — free events are excluded
        busy_events = [e for e in all_events if e.get("availability", "busy") != "free"]

        merged = self._build_busy_blocks(busy_events)
        free_slots = self._calculate_free_slots(merged, range_start, range_end)

        return self._apply_availability_filters(free_slots, wh, min_duration_minutes)

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
        all_events = self.get_events(calendar_names or [], start_date, end_date)

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
        self._validate_cli_arg(name, "name")
        return self._run_swift_helper_json("create_calendar", ["--name", name])

    def delete_calendar(
        self, name: str, calendar_source: str = ""
    ) -> dict[str, str]:
        """Delete a calendar from Apple Calendar.

        Uses EventKit via Swift helper for native calendar deletion.

        Args:
            name: Name of the calendar to delete
            calendar_source: Source/account name to disambiguate duplicates

        Returns:
            Dict with 'name' key of the deleted calendar

        Raises:
            CalendarSafetyError: If safety checks block the target calendar
            ValueError: If the calendar doesn't exist or is ambiguous
            PermissionError: If EventKit calendar access is denied
        """
        self._verify_calendar_safety(name)
        self._validate_cli_arg(name, "name")
        if calendar_source:
            self._validate_cli_arg(calendar_source, "calendar_source")
        args = ["--name", name]
        if calendar_source:
            args += ["--source", calendar_source]
        return self._run_swift_helper_json("delete_calendar", args)
