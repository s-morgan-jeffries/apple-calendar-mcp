"""FastMCP Server for Apple Calendar integration."""
import json
import os
from typing import Optional

from fastmcp import FastMCP

from .calendar_connector import CalendarConnector

# Create FastMCP server
mcp = FastMCP("apple-calendar-mcp", instructions="""Apple Calendar is the built-in macOS calendar application. This MCP server provides tools to interact with it.

CALENDARS: Each calendar has a name, writable status, description, and color. Calendar names are NOT guaranteed unique — the same name can appear across different accounts (e.g., two "Family" calendars from iCloud and Google). Use description to disambiguate when needed.

CALENDAR IDENTIFICATION: Calendars are identified by name (not UID — UIDs are not accessible via AppleScript). When specifying a calendar, use the exact name as returned by get_calendars.

EVENTS: Events have summary (title), start/end dates, location, description (notes), URL, status, and recurrence. Events are identified by their UID (UUID format).

RECURRING EVENTS: Recurring events share the same UID across all occurrences. Each occurrence has a unique occurrence_date. The is_recurring field indicates if an event is part of a series. The recurrence_rule field contains the iCalendar RRULE (e.g., "FREQ=WEEKLY;INTERVAL=1;BYDAY=MO,WE,FR"). Note: update_event by UID modifies the entire series — single-occurrence modification is not yet supported.

DATES: All dates use ISO 8601 format (e.g., "2026-03-15" or "2026-03-15T14:30:00"). The server handles conversion to/from AppleScript's locale-dependent date format.
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

    Note: Calendar names may not be unique across accounts. Check the description
    field to distinguish calendars with the same name from different accounts.
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
    """
    client = get_client()
    try:
        result = client.delete_calendar(name=name)
    except Exception as e:
        return f"Error deleting calendar: {e}"
    return f"Deleted calendar '{result['name']}'"


@mcp.tool()
def create_event(
    calendar_name: str,
    summary: str,
    start_date: str,
    end_date: str,
    location: str = "",
    description: str = "",
    url: str = "",
    allday_event: bool = False,
    recurrence_rule: str = "",
) -> str:
    """Create a new event in a specified calendar.

    Args:
        calendar_name: Exact name of the target calendar (use get_calendars to find available names)
        summary: Event title
        start_date: Start date/time in ISO 8601 format (e.g., "2026-03-15" for all-day, "2026-03-15T14:30:00" for timed)
        end_date: End date/time in ISO 8601 format (must be after start_date)
        location: Event location (optional)
        description: Event notes/description (optional)
        url: URL associated with the event (optional)
        allday_event: Whether this is an all-day event (default: false). When true, use date-only format for start_date/end_date.
        recurrence_rule: iCalendar RRULE string for recurring events (optional, e.g., "FREQ=WEEKLY;BYDAY=MO,WE,FR" or "FREQ=DAILY;COUNT=10")
    """
    client = get_client()
    try:
        event_uid = client.create_event(
            calendar_name=calendar_name,
            summary=summary,
            start_date=start_date,
            end_date=end_date,
            location=location or None,
            description=description or None,
            url=url or None,
            allday_event=allday_event,
            recurrence_rule=recurrence_rule or None,
        )
    except Exception as e:
        return f"Error creating event: {e}"

    result = f"Created event '{summary}' in calendar '{calendar_name}'\nEvent UID: {event_uid}"
    if location:
        result += f"\nLocation: {location}"
    if allday_event:
        result += "\nAll-day event"
    if recurrence_rule:
        result += f"\nRecurrence: {recurrence_rule}"
    return result


def _format_event(event: dict) -> str:
    """Format an event dict as human-readable text."""
    result = f"Title: {event['summary']}\n"
    result += f"Start: {event['start_date']}\n"
    result += f"End: {event['end_date']}\n"
    if event.get("allday_event"):
        result += "All-day event\n"
    if event.get("location"):
        result += f"Location: {event['location']}\n"
    if event.get("description"):
        result += f"Description: {event['description']}\n"
    if event.get("url"):
        result += f"URL: {event['url']}\n"
    if event.get("is_recurring"):
        result += f"Recurring: {event.get('recurrence_rule', 'yes')}\n"
        if event.get("is_detached"):
            result += "Modified occurrence (detached from series)\n"
    result += f"Status: {event.get('status', 'none')}\n"
    result += f"UID: {event['uid']}\n"
    return result


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
) -> str:
    """Find free time slots across one or more calendars.

    Queries all specified calendars, merges busy periods, and returns
    available (free) time slots within the date range. Useful for scheduling.

    Use get_calendars first to find available calendar names.

    Args:
        calendar_names: List of calendar names to check for combined availability
        start_date: Start of range in ISO 8601 format (e.g., "2026-03-15T09:00:00")
        end_date: End of range in ISO 8601 format (e.g., "2026-03-15T17:00:00")
    """
    client = get_client()
    try:
        slots = client.get_availability(
            calendar_names=calendar_names,
            start_date=start_date,
            end_date=end_date,
        )
    except Exception as e:
        return f"Error checking availability: {e}"

    cal_list = ", ".join(f"'{c}'" for c in calendar_names)
    if not slots:
        return f"No free time in {cal_list} between {start_date} and {end_date}."

    lines = [_format_free_slot(slot) for slot in slots]
    return f"Found {len(slots)} free slot(s) across {cal_list}:\n\n" + "\n".join(lines)


@mcp.tool()
def update_event(
    calendar_name: str,
    event_uid: str,
    summary: str | None = None,
    start_date: str | None = None,
    end_date: str | None = None,
    location: str | None = None,
    description: str | None = None,
    url: str | None = None,
    allday_event: bool | None = None,
) -> str:
    """Update an existing event's properties by UID.

    Only provided fields are updated; omitted fields are left unchanged.
    To clear a text field (location, description, url), pass an empty string "".

    Use get_events first to find the event's UID and calendar_name.

    Args:
        calendar_name: Exact name of the calendar containing the event
        event_uid: UID of the event to update (from get_events results)
        summary: New event title (optional)
        start_date: New start date/time in ISO 8601 format (optional)
        end_date: New end date/time in ISO 8601 format (optional)
        location: New location, or "" to clear (optional)
        description: New description/notes, or "" to clear (optional)
        url: New URL, or "" to clear (optional)
        allday_event: New all-day status (optional)
    """
    client = get_client()
    try:
        result = client.update_event(
            calendar_name=calendar_name,
            event_uid=event_uid,
            summary=summary,
            start_date=start_date,
            end_date=end_date,
            location=location,
            description=description,
            url=url,
            allday_event=allday_event,
        )
    except Exception as e:
        return f"Error updating event: {e}"

    fields_str = ", ".join(result["updated_fields"])
    return f"Updated event {event_uid} in calendar '{calendar_name}'\nUpdated fields: {fields_str}"


@mcp.tool()
def delete_events(
    calendar_name: str,
    event_uid: str | list[str],
) -> str:
    """Delete one or more events from a calendar by UID.

    Accepts a single UID or a list of UIDs for batch deletion. Events that
    don't exist are reported but don't cause the entire operation to fail.

    Use get_events first to find the event UID(s) and calendar_name.

    Args:
        calendar_name: Exact name of the calendar containing the event(s)
        event_uid: UID of a single event (str) or list of UIDs to delete
    """
    client = get_client()
    try:
        result = client.delete_events(
            calendar_name=calendar_name,
            event_uids=event_uid,
        )
    except Exception as e:
        return f"Error deleting event(s): {e}"

    deleted = result["deleted_uids"]
    not_found = result["not_found_uids"]

    msg = f"Deleted {len(deleted)} event(s) from calendar '{calendar_name}'"
    if not_found:
        msg += f"\nNot found ({len(not_found)}): {', '.join(not_found)}"
    return msg
