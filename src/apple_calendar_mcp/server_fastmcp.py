"""FastMCP Server for Apple Calendar integration."""
import json
import os
from typing import Optional

from fastmcp import FastMCP

from .calendar_connector import CalendarConnector

# Create FastMCP server
mcp = FastMCP("apple-calendar-mcp", instructions="""Apple Calendar is the built-in macOS calendar application. This MCP server provides tools to interact with it.

CALENDARS: Each calendar has a name, writable status, type (caldav, subscription, birthday, local), source (account name like "iCloud" or "Google"), description, and color. Calendar names are NOT guaranteed unique — the same name can appear across different accounts (e.g., two "Family" calendars from iCloud and Google). Use the source field to disambiguate when needed.

CALENDAR IDENTIFICATION: Calendars are identified by name (not UID — UIDs are not accessible via AppleScript). When specifying a calendar, use the exact name as returned by get_calendars.

EVENTS: Events have summary (title), start/end dates, location, notes, URL, status, recurrence, attendees, and editability info. Events are identified by their UID (UUID format). The is_editable field indicates whether the event can be modified — events on read-only calendars or events where you are not the organizer (invited events) are not editable. Attendees are read-only — they cannot be added via this server (use Calendar.app or email invitations).

RECURRING EVENTS: Recurring events share the same UID across all occurrences. Each occurrence has a unique occurrence_date. The is_recurring field indicates if an event is part of a series. The recurrence_rule field contains the iCalendar RRULE (e.g., "FREQ=WEEKLY;INTERVAL=1;BYDAY=MO,WE,FR"). To modify or delete a specific occurrence, pass occurrence_date and span="this_event". To modify or delete the series from a point onward, use span="future_events".

DATES: All dates use ISO 8601 format in local time, without timezone suffix (e.g., "2026-03-15" or "2026-03-15T14:30:00"). Returned event timestamps are also in local time. Do NOT append "Z" to dates — they are not UTC.
""")

# Initialize Calendar client (lazy)
_client: Optional[CalendarConnector] = None


def get_client() -> CalendarConnector:
    """Get or create the Calendar client.

    Safety checks are enabled only when CALENDAR_TEST_MODE=true (integration tests).
    In production (Claude Desktop), safety checks are off so all calendars are writable.
    """
    global _client
    if _client is None:
        _test_mode = os.environ.get("CALENDAR_TEST_MODE") == "true"
        _client = CalendarConnector(enable_safety_checks=_test_mode)
    return _client


def _format_calendar(cal: dict) -> str:
    """Format a calendar dict as human-readable text."""
    writable = "read-write" if cal["writable"] else "read-only"
    result = f"Name: {cal['name']}\n"
    result += f"Access: {writable}\n"
    if cal.get("source"):
        result += f"Source: {cal['source']}\n"
    if cal.get("description"):
        result += f"Description: {cal['description']}\n"
    result += f"Color: {cal['color']}\n"
    return result


@mcp.tool()
def get_calendars() -> str:
    """List all calendars in Apple Calendar.

    Returns all calendars with their names, access level (read-write or read-only),
    descriptions, and colors. Use this to discover available calendars before
    creating or querying events.

    Note: Calendar names may not be unique across accounts. Use the source field
    (e.g., "iCloud", "Google") to distinguish calendars with the same name from
    different accounts.

    Returns:
        Each calendar includes: name, access level (read-write or read-only), source
        (account name like "iCloud" or "Google"), description, color.
        Use calendar names exactly as shown when calling other tools.
    """
    client = get_client()
    calendars = client.get_calendars()

    if not calendars:
        return "No calendars found."

    lines = []
    for cal in calendars:
        lines.append(_format_calendar(cal))

    return f"Found {len(calendars)} calendar(s):\n\n" + "\n".join(lines)


@mcp.tool()
def create_calendar(name: str) -> str:
    """Create a new calendar in Apple Calendar.

    Args:
        name: Name for the new calendar

    Returns:
        Confirmation with the calendar name.
    """
    client = get_client()
    try:
        result = client.create_calendar(name=name)
    except Exception as e:
        return f"Error creating calendar: {e}"
    return f"Created calendar '{result['name']}'"


@mcp.tool()
def delete_calendar(name: str) -> str:
    """Delete a calendar from Apple Calendar.

    This permanently removes the calendar and all its events. Use with caution.

    Args:
        name: Exact name of the calendar to delete (use get_calendars to find available names)

    Returns:
        Confirmation with the deleted calendar name.
    """
    client = get_client()
    try:
        result = client.delete_calendar(name=name)
    except Exception as e:
        return f"Error deleting calendar: {e}"
    return f"Deleted calendar '{result['name']}'"


def _parse_alert_minutes(alert_minutes: str) -> list[int] | None:
    """Parse comma-separated alert minutes string into a list of ints."""
    if not alert_minutes:
        return None
    try:
        return [int(m.strip()) for m in alert_minutes.split(",") if m.strip()]
    except ValueError:
        raise ValueError(
            f"alert_minutes must be comma-separated integers (e.g., '15,60'), got: {alert_minutes!r}"
        )


def _build_create_response(
    summary: str, calendar_name: str, event_uid: str,
    location: str, allday_event: bool, recurrence_rule: str,
) -> str:
    """Build the success response for create_event."""
    lines = [f"Created event '{summary}' in calendar '{calendar_name}'", f"Event UID: {event_uid}"]
    if location:
        lines.append(f"Location: {location}")
    if allday_event:
        lines.append("All-day event")
    if recurrence_rule:
        lines.append(f"Recurrence: {recurrence_rule}")
    return "\n".join(lines)


@mcp.tool()
def create_event(
    calendar_name: str,
    summary: str,
    start_date: str,
    end_date: str,
    location: str = "",
    notes: str = "",
    url: str = "",
    allday_event: bool = False,
    recurrence_rule: str = "",
    alert_minutes: str = "",
    availability: str = "",
    timezone: str = "",
) -> str:
    """Create a new event in a specified calendar.

    Args:
        calendar_name: Exact name of the target calendar (use get_calendars to find available names)
        summary: Event title
        start_date: Start date/time in ISO 8601 format (e.g., "2026-03-15" for all-day, "2026-03-15T14:30:00" for timed)
        end_date: End date/time in ISO 8601 format (must be after start_date)
        location: Event location (optional)
        notes: Event notes (optional)
        url: URL associated with the event (optional)
        allday_event: Whether this is an all-day event (default: false). When true, use date-only format for start_date/end_date. For a single-day event, end_date equals start_date. For multi-day events, end_date is the last day (inclusive).
        recurrence_rule: iCalendar RRULE string for recurring events (optional, e.g., "FREQ=WEEKLY;BYDAY=MO,WE,FR" or "FREQ=DAILY;COUNT=10")
        alert_minutes: Comma-separated minutes before event to alert (optional, e.g., "15" or "15,60")
        availability: Event availability status: "free", "busy", or "tentative" (optional, default: busy)
        timezone: IANA timezone for interpreting start/end times (optional, e.g., "America/Los_Angeles", "US/Eastern"). When provided, times are interpreted in that timezone instead of the system's local timezone.

    Returns:
        Confirmation with the event UID. Use this UID with update_event or delete_events.
        If recurrence_rule was set, includes the recurrence details.
        If alert_minutes was set, includes the alert times.
    """
    client = get_client()
    try:
        event_uid = client.create_event(
            calendar_name=calendar_name,
            summary=summary,
            start_date=start_date,
            end_date=end_date,
            location=location or None,
            notes=notes or None,
            url=url or None,
            allday_event=allday_event,
            recurrence_rule=recurrence_rule or None,
            alert_minutes=_parse_alert_minutes(alert_minutes),
            availability=availability or None,
            timezone=timezone or None,
        )
    except Exception as e:
        return f"Error creating event: {e}"

    return _build_create_response(summary, calendar_name, event_uid, location, allday_event, recurrence_rule)


@mcp.tool()
def create_events(
    calendar_name: str,
    events: str,
) -> str:
    """Create multiple events in a single batch operation.

    More efficient than calling create_event multiple times — all events are
    created in one operation. All events go to the same calendar.

    Args:
        calendar_name: Exact name of the target calendar
        events: JSON array of event objects. Each object has keys: summary (required),
                start (required, ISO 8601), end (required, ISO 8601), and optional:
                location, notes, url, allday (bool — when true, end is the last day inclusive),
                recurrence (RRULE string), alerts (list of minutes, e.g. [15, 60]),
                availability ("free"/"busy"/"tentative"),
                timezone (IANA identifier, e.g. "America/Los_Angeles")

    Returns:
        Summary of created events, each with title and UID. Any per-event errors are listed
        separately. Partial success is possible — some events may be created while others fail.
    """
    try:
        event_list = json.loads(events)
    except json.JSONDecodeError as e:
        return f"Error: invalid JSON for events parameter: {e}"

    if not isinstance(event_list, list):
        return "Error: events must be a JSON array"

    client = get_client()
    try:
        result = client.create_events(
            calendar_name=calendar_name,
            events=event_list,
        )
    except Exception as e:
        return f"Error creating events: {e}"

    created = result.get("created", [])
    errors = result.get("errors", [])

    parts = [f"Created {len(created)} event(s) in calendar '{calendar_name}'"]
    for c in created:
        parts.append(f"  {c['summary']} (UID: {c['uid']})")
    if errors:
        parts.append(f"\n{len(errors)} error(s):")
        for e in errors:
            parts.append(f"  [{e.get('index', '?')}] {e.get('summary', '?')}: {e.get('error', '?')}")
    return "\n".join(parts)


@mcp.tool()
def update_events(
    calendar_name: str,
    updates: str,
) -> str:
    """Update multiple events in a single batch operation.

    More efficient than calling update_event multiple times. All events must be
    on the same calendar.

    Args:
        calendar_name: Exact name of the calendar containing the events
        updates: JSON array of update objects. Each object must have "uid" (required)
                 and at least one field to update: summary, start (ISO 8601), end (ISO 8601),
                 location, notes, url, allday (bool — when true, end is the last day inclusive),
                 alerts (list of minutes), availability ("free"/"busy"/"tentative"),
                 timezone (IANA identifier), recurrence (RRULE string), clear_location (bool),
                 clear_notes (bool), clear_url (bool), clear_alerts (bool), clear_recurrence (bool)

    Returns:
        Summary of updated events, each with title and list of changed fields. Any per-event
        errors are listed separately. Partial success is possible.
    """
    try:
        update_list = json.loads(updates)
    except json.JSONDecodeError as e:
        return f"Error: invalid JSON for updates parameter: {e}"

    if not isinstance(update_list, list):
        return "Error: updates must be a JSON array"

    client = get_client()
    try:
        result = client.update_events(
            calendar_name=calendar_name,
            updates=update_list,
        )
    except Exception as e:
        return f"Error updating events: {e}"

    updated = result.get("updated", [])
    errors = result.get("errors", [])

    parts = [f"Updated {len(updated)} event(s) in calendar '{calendar_name}'"]
    for u in updated:
        fields = ", ".join(u.get("updated_fields", []))
        parts.append(f"  {u.get('summary', '?')} — {fields}")
    if errors:
        parts.append(f"\n{len(errors)} error(s):")
        for e in errors:
            parts.append(f"  [{e.get('index', '?')}] {e.get('uid', '?')}: {e.get('error', '?')}")
    return "\n".join(parts)


def _format_event_details(event: dict) -> list[str]:
    """Format optional event fields as a list of display lines."""
    lines: list[str] = []
    if event.get("allday_event"):
        lines.append("All-day event")
    for key, label in [("location", "Location"), ("notes", "Notes"), ("url", "URL")]:
        if event.get(key):
            lines.append(f"{label}: {event[key]}")
    lines += _format_recurrence(event)
    lines += _format_alerts(event.get("alerts", []))
    lines += _format_attendees(event.get("attendees", []))
    avail = event.get("availability", "busy")
    if avail and avail != "busy":
        lines.append(f"Availability: {avail}")
    return lines


def _format_recurrence(event: dict) -> list[str]:
    """Format recurrence info for an event."""
    if not event.get("is_recurring"):
        return []
    lines = [f"Recurring: {event.get('recurrence_rule', 'yes')}"]
    if event.get("is_detached"):
        lines.append("Modified occurrence (detached from series)")
    return lines


def _format_alerts(alerts: list[dict]) -> list[str]:
    """Format alert list for display."""
    if not alerts:
        return []
    alert_strs = [f"{a['minutes_before']}m before" for a in alerts]
    return [f"Alerts: {', '.join(alert_strs)}"]


def _format_attendees(attendees: list[dict]) -> list[str]:
    """Format attendee list for display."""
    if not attendees:
        return []
    names = [a.get("name") or a.get("email", "unknown") for a in attendees]
    return [f"Attendees ({len(attendees)}): {', '.join(names)}"]


def _format_event(event: dict) -> str:
    """Format an event dict as human-readable text."""
    lines = [
        f"Title: {event['summary']}",
        f"Start: {event['start_date']}",
        f"End: {event['end_date']}",
        *_format_event_details(event),
        f"Status: {event.get('status', 'none')}",
        f"UID: {event['uid']}",
    ]
    return "\n".join(lines) + "\n"


@mcp.tool()
def get_events(
    calendar_name: str,
    start_date: str,
    end_date: str,
) -> str:
    """Get events from a calendar within a date range.

    Returns all events in the specified calendar that overlap with the given
    date range. Use get_calendars first to find available calendar names.

    Args:
        calendar_name: Exact name of the calendar to query (use get_calendars to find available names)
        start_date: Start of date range in ISO 8601 format (e.g., "2026-03-15" or "2026-03-15T00:00:00")
        end_date: End of date range in ISO 8601 format (must be after start_date)

    Returns:
        Each event includes: uid, summary, start_date, end_date, allday_event, location, notes,
        url, status, calendar_name, availability.
        For all-day events, end_date is the last day of the event (inclusive).
        For recurring events: is_recurring, recurrence_rule, occurrence_date, is_detached.
        If alerts are set: alerts (list with minutes_before for each).
        If attendees exist: attendees (list with name, email, role, status for each).
        `uid` and `calendar_name` identify the event for update_event and delete_events.
        For recurring events, also use `occurrence_date` to target a specific occurrence.
    """
    client = get_client()
    try:
        events = client.get_events(
            calendar_name=calendar_name,
            start_date=start_date,
            end_date=end_date,
        )
    except Exception as e:
        return f"Error getting events: {e}"

    if not events:
        return f"No events found in '{calendar_name}' between {start_date} and {end_date}."

    lines = []
    for event in events:
        lines.append(_format_event(event))

    return f"Found {len(events)} event(s) in '{calendar_name}':\n\n" + "\n".join(lines)


@mcp.tool()
def search_events(
    query: str,
    calendar_name: str = "",
    start_date: str = "",
    end_date: str = "",
) -> str:
    """Search events by text across one or all calendars.

    Searches event summaries, notes, and locations with case-insensitive
    matching. If no calendar is specified, searches all calendars. If no date
    range is specified, searches from 1 month ago to 6 months from now.

    Args:
        query: Text to search for in event titles, notes, and locations
        calendar_name: Calendar to search (optional — searches all calendars if empty)
        start_date: Start of date range in ISO 8601 format (optional)
        end_date: End of date range in ISO 8601 format (optional)

    Returns:
        Matching events with the same fields as get_events. Returns events whose summary,
        notes, or location contain the query text (case-insensitive).
    """
    client = get_client()
    try:
        events = client.search_events(
            query=query,
            calendar_name=calendar_name or None,
            start_date=start_date or None,
            end_date=end_date or None,
        )
    except Exception as e:
        return f"Error searching events: {e}"

    if not events:
        scope = f"in '{calendar_name}'" if calendar_name else "across all calendars"
        return f"No events matching '{query}' found {scope}."

    lines = [_format_event(event) for event in events]
    scope = f"in '{calendar_name}'" if calendar_name else "across all calendars"
    return f"Found {len(events)} event(s) matching '{query}' {scope}:\n\n" + "\n".join(lines)


def _format_free_slot(slot: dict) -> str:
    """Format a free time slot as human-readable text."""
    hours = slot["duration_minutes"] // 60
    minutes = slot["duration_minutes"] % 60
    if hours and minutes:
        duration = f"{hours}h {minutes}m"
    elif hours:
        duration = f"{hours}h"
    else:
        duration = f"{minutes}m"
    return f"{slot['start_date']} to {slot['end_date']} ({duration})"


@mcp.tool()
def get_availability(
    calendar_names: list[str],
    start_date: str,
    end_date: str,
    min_duration_minutes: int | None = None,
    working_hours_start: str | None = None,
    working_hours_end: str | None = None,
) -> str:
    """Find free time slots across one or more calendars.

    Queries all specified calendars, merges busy periods, and returns
    available (free) time slots within the date range. Useful for scheduling.

    Use get_calendars first to find available calendar names.

    Args:
        calendar_names: List of calendar names to check for combined availability
        start_date: Start of range in ISO 8601 format (e.g., "2026-03-15T09:00:00")
        end_date: End of range in ISO 8601 format (e.g., "2026-03-15T17:00:00")
        min_duration_minutes: Only return slots of at least this many minutes (e.g., 45)
        working_hours_start: Start of working hours as HH:MM (e.g., "09:00")
        working_hours_end: End of working hours as HH:MM (e.g., "17:00")

    Returns:
        Each free slot includes: start_date, end_date, duration (formatted as hours and minutes).
        Slots are gaps between busy periods across all specified calendars. Overlapping events
        are merged. Returns "No free time" if the entire range is busy.
    """
    client = get_client()
    try:
        slots = client.get_availability(
            calendar_names=calendar_names,
            start_date=start_date,
            end_date=end_date,
            min_duration_minutes=min_duration_minutes,
            working_hours_start=working_hours_start,
            working_hours_end=working_hours_end,
        )
    except Exception as e:
        return f"Error checking availability: {e}"

    cal_list = ", ".join(f"'{c}'" for c in calendar_names)
    filters = []
    if min_duration_minutes:
        filters.append(f">= {min_duration_minutes} min")
    if working_hours_start and working_hours_end:
        filters.append(f"{working_hours_start}-{working_hours_end}")
    filter_desc = f" ({', '.join(filters)})" if filters else ""

    if not slots:
        return f"No free time in {cal_list} between {start_date} and {end_date}{filter_desc}."

    lines = [_format_free_slot(slot) for slot in slots]
    return f"Found {len(slots)} free slot(s) across {cal_list}{filter_desc}:\n\n" + "\n".join(lines)


def _format_conflict(conflict: dict) -> str:
    """Format a conflict pair as human-readable text."""
    a = conflict["event_a"]
    b = conflict["event_b"]
    overlap = f"{conflict['overlap_start']} to {conflict['overlap_end']}"
    lines = [
        f"{conflict['overlap_minutes']} min overlap ({overlap}):",
        f"  \"{a['summary']}\" on {a['calendar_name']} ({a['start_date']} to {a['end_date']})",
        f"  \"{b['summary']}\" on {b['calendar_name']} ({b['start_date']} to {b['end_date']})",
    ]
    return "\n".join(lines)


@mcp.tool()
def get_conflicts(
    calendar_names: list[str],
    start_date: str,
    end_date: str,
) -> str:
    """Detect double-bookings and overlapping events across calendars.

    Finds all pairs of events that overlap in time within the date range.
    Useful for checking if you have scheduling conflicts before adding new events.

    Use get_calendars first to find available calendar names.

    Args:
        calendar_names: List of calendar names to check for conflicts
        start_date: Start of range in ISO 8601 format (e.g., "2026-03-15T00:00:00")
        end_date: End of range in ISO 8601 format (e.g., "2026-03-22T00:00:00")

    Returns:
        Each conflict includes two overlapping events with their UIDs, summaries,
        times, and calendar names, plus the overlap window and duration in minutes.
        Events marked as "free" availability are excluded. Returns "No conflicts"
        if no overlapping events found.
    """
    client = get_client()
    try:
        conflicts = client.get_conflicts(
            calendar_names=calendar_names,
            start_date=start_date,
            end_date=end_date,
        )
    except Exception as e:
        return f"Error checking conflicts: {e}"

    cal_list = ", ".join(f"'{c}'" for c in calendar_names)

    if not conflicts:
        return f"No conflicts found in {cal_list} between {start_date} and {end_date}."

    lines = [_format_conflict(c) for c in conflicts]
    return f"Found {len(conflicts)} conflict(s) across {cal_list}:\n\n" + "\n\n".join(lines)


@mcp.tool()
def update_event(
    calendar_name: str,
    event_uid: str,
    summary: str | None = None,
    start_date: str | None = None,
    end_date: str | None = None,
    location: str | None = None,
    notes: str | None = None,
    url: str | None = None,
    allday_event: bool | None = None,
    alert_minutes: str = "",
    availability: str | None = None,
    timezone: str = "",
    recurrence_rule: str | None = None,
    occurrence_date: str = "",
    span: str = "this_event",
) -> str:
    """Update an existing event's properties by UID.

    Only provided fields are updated; omitted fields are left unchanged.
    To clear a text field (location, notes, url), pass an empty string "".

    Use get_events first to find the event's UID and calendar_name.

    For recurring events: use occurrence_date to target a specific occurrence,
    and span to control whether the change affects just this occurrence or the series.

    Args:
        calendar_name: Exact name of the calendar containing the event
        event_uid: UID of the event to update (from get_events results)
        summary: New event title (optional)
        start_date: New start date/time in ISO 8601 format (optional)
        end_date: New end date/time in ISO 8601 format (optional)
        location: New location, or "" to clear (optional)
        notes: New notes, or "" to clear (optional)
        url: New URL, or "" to clear (optional)
        allday_event: New all-day status (optional). When true, end_date is the last day (inclusive).
        alert_minutes: Comma-separated minutes before event to alert (e.g., "15,60"), or "none" to clear all alerts (optional)
        availability: Event availability: "free", "busy", or "tentative" (optional)
        recurrence_rule: iCalendar RRULE string to set/change recurrence (e.g., "FREQ=WEEKLY;BYDAY=MO,WE,FR"), or "" to remove recurrence (optional)
        occurrence_date: For recurring events, the occurrence_date from get_events to target a specific occurrence (optional)
        span: "this_event" to update one occurrence, "future_events" to update this and all future occurrences (default: "this_event")

    Returns:
        Confirmation with the event UID and list of updated fields.
        Note: when rescheduling a single occurrence of a recurring event (changing dates with
        span="this_event"), a new standalone event is created — the returned UID may differ
        from the original.
    """
    parsed_alerts = None
    if alert_minutes == "none":
        parsed_alerts = []
    elif alert_minutes:
        parsed_alerts = _parse_alert_minutes(alert_minutes)
    # recurrence_rule: None = not provided, "" = clear, "RRULE..." = set
    parsed_recurrence = None
    if recurrence_rule is not None:
        parsed_recurrence = recurrence_rule  # pass through as-is (empty string = clear)
    client = get_client()
    try:
        result = client.update_event(
            calendar_name=calendar_name,
            event_uid=event_uid,
            summary=summary,
            start_date=start_date,
            end_date=end_date,
            location=location,
            notes=notes,
            url=url,
            allday_event=allday_event,
            alert_minutes=parsed_alerts,
            availability=availability,
            timezone=timezone or None,
            recurrence_rule=parsed_recurrence,
            occurrence_date=occurrence_date or None,
            span=span,
        )
    except Exception as e:
        return f"Error updating event: {e}"

    fields_str = ", ".join(result["updated_fields"])
    return f"Updated event {event_uid} in calendar '{calendar_name}'\nUpdated fields: {fields_str}"


@mcp.tool()
def delete_events(
    calendar_name: str,
    event_uid: str | list[str],
    span: str = "this_event",
    occurrence_date: str = "",
) -> str:
    """Delete one or more events from a calendar by UID.

    Accepts a single UID or a list of UIDs for batch deletion. Events that
    don't exist are reported but don't cause the entire operation to fail.

    Use get_events first to find the event UID(s) and calendar_name.

    For recurring events: use occurrence_date to target a specific occurrence,
    and span to control deletion scope. Without occurrence_date, deletes the
    base event (which may affect the entire series).

    Args:
        calendar_name: Exact name of the calendar containing the event(s)
        event_uid: UID of a single event (str) or list of UIDs to delete
        span: "this_event" to delete one occurrence, "future_events" to delete the series from this point onward (default: "this_event")
        occurrence_date: For recurring events, the occurrence_date from get_events to target a specific occurrence (optional)

    Returns:
        Count of deleted events. Any UIDs not found are listed separately — these don't cause
        the operation to fail.
    """
    client = get_client()
    try:
        result = client.delete_events(
            calendar_name=calendar_name,
            event_uids=event_uid,
            span=span,
            occurrence_date=occurrence_date or None,
        )
    except Exception as e:
        return f"Error deleting event(s): {e}"

    deleted = result["deleted_uids"]
    not_found = result["not_found_uids"]

    msg = f"Deleted {len(deleted)} event(s) from calendar '{calendar_name}'"
    if not_found:
        msg += f"\nNot found ({len(not_found)}): {', '.join(not_found)}"
    return msg
