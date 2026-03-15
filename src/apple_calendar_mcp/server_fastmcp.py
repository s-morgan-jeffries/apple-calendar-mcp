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

DATES: All dates use ISO 8601 format (e.g., "2026-03-15" or "2026-03-15T14:30:00"). The server handles conversion to/from AppleScript's locale-dependent date format.
""")

# Initialize Calendar client (lazy)
_client: Optional[CalendarConnector] = None


def get_client() -> CalendarConnector:
    """Get or create the Calendar client."""
    global _client
    if _client is None:
        _in_pytest = os.environ.get("PYTEST_CURRENT_TEST") is not None
        _client = CalendarConnector(enable_safety_checks=not _in_pytest)
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
def create_event(
    calendar_name: str,
    summary: str,
    start_date: str,
    end_date: str,
    location: str = "",
    description: str = "",
    url: str = "",
    allday_event: bool = False,
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
        )
    except Exception as e:
        return f"Error creating event: {e}"

    result = f"Created event '{summary}' in calendar '{calendar_name}'\nEvent UID: {event_uid}"
    if location:
        result += f"\nLocation: {location}"
    if allday_event:
        result += "\nAll-day event"
    return result
