# Apple Calendar MCP — Tool Descriptions

This file contains exactly what an MCP-connected agent sees: the server instructions and all tool schemas with docstrings. Used as input for blind agent eval.

## Server Instructions

Apple Calendar is the built-in macOS calendar application. This MCP server provides tools to interact with it.

CALENDARS: Each calendar has a name, writable status, type (caldav, subscription, birthday, local), description, and color. Calendar names are NOT guaranteed unique — the same name can appear across different accounts (e.g., two "Family" calendars from iCloud and Google). Use description to disambiguate when needed.

CALENDAR IDENTIFICATION: Calendars are identified by name (not UID — UIDs are not accessible via AppleScript). When specifying a calendar, use the exact name as returned by get_calendars.

EVENTS: Events have summary (title), start/end dates, location, notes, URL, status, recurrence, attendees, and editability info. Events are identified by their UID (UUID format). The is_editable field indicates whether the event can be modified — events on read-only calendars or events where you are not the organizer (invited events) are not editable. Attendees are read-only — they cannot be added via this server (use Calendar.app or email invitations).

RECURRING EVENTS: Recurring events share the same UID across all occurrences. Each occurrence has a unique occurrence_date. The is_recurring field indicates if an event is part of a series. The recurrence_rule field contains the iCalendar RRULE (e.g., "FREQ=WEEKLY;INTERVAL=1;BYDAY=MO,WE,FR"). To modify or delete a specific occurrence, pass occurrence_date and span="this_event". To modify or delete the series from a point onward, use span="future_events".

DATES: All dates use ISO 8601 format in local time, without timezone suffix (e.g., "2026-03-15" or "2026-03-15T14:30:00"). Returned event timestamps are also in local time. Do NOT append "Z" to dates — they are not UTC.

---

## Tools

### get_calendars

List all calendars in Apple Calendar.

Returns all calendars with their names, access level (read-write or read-only), source (account name), descriptions, and colors. Use this to discover available calendars before creating or querying events.

Note: Calendar names may not be unique across accounts. Use the source field (e.g., "iCloud", "Google") to distinguish calendars with the same name from different accounts.

**Returns:** Each calendar includes: name, access level (read-write or read-only), source (account name like "iCloud" or "Google"), description, color. Use calendar names exactly as shown when calling other tools.

**Parameters:** None

---

### create_calendar

Create a new calendar in Apple Calendar.

**Parameters:**
- `name` (str, required): Name for the new calendar

**Returns:** Confirmation with the calendar name.

---

### delete_calendar

Delete a calendar from Apple Calendar.

This permanently removes the calendar and all its events. Use with caution.

**Parameters:**
- `name` (str, required): Exact name of the calendar to delete (use get_calendars to find available names)

**Returns:** Confirmation with the deleted calendar name.

---

### create_event

Create a new event in a specified calendar.

**Parameters:**
- `calendar_name` (str, required): Exact name of the target calendar (use get_calendars to find available names)
- `summary` (str, required): Event title
- `start_date` (str, required): Start date/time in ISO 8601 format (e.g., "2026-03-15" for all-day, "2026-03-15T14:30:00" for timed)
- `end_date` (str, required): End date/time in ISO 8601 format (must be after start_date)
- `location` (str, optional, default: ""): Event location
- `notes` (str, optional, default: ""): Event notes
- `url` (str, optional, default: ""): URL associated with the event
- `allday_event` (bool, optional, default: false): Whether this is an all-day event. When true, use date-only format for start_date/end_date.
- `recurrence_rule` (str, optional, default: ""): iCalendar RRULE string for recurring events (e.g., "FREQ=WEEKLY;BYDAY=MO,WE,FR" or "FREQ=DAILY;COUNT=10")
- `alert_minutes` (str, optional, default: ""): Comma-separated minutes before event to alert (e.g., "15" or "15,60")
- `availability` (str, optional, default: ""): Event availability status: "free", "busy", or "tentative" (default: busy)
- `timezone` (str, optional, default: ""): IANA timezone for interpreting start/end times (e.g., "America/Los_Angeles", "US/Eastern"). When provided, times are interpreted in that timezone instead of the system's local timezone.

**Returns:** Confirmation with the event UID. Use this UID with update_event or delete_events. If recurrence_rule was set, includes the recurrence details. If alert_minutes was set, includes the alert times.

---

### create_events

Create multiple events in a single batch operation.

More efficient than calling create_event multiple times — all events are created in one operation. All events go to the same calendar.

**Parameters:**
- `calendar_name` (str, required): Exact name of the target calendar
- `events` (str, required): JSON array of event objects. Each object has keys: summary (required), start (required, ISO 8601), end (required, ISO 8601), and optional: location, notes, url, allday (bool), recurrence (RRULE string), alerts (list of minutes, e.g. [15, 60]), availability ("free"/"busy"/"tentative"), timezone (IANA identifier, e.g. "America/Los_Angeles")

**Returns:** Summary of created events, each with title and UID. Any per-event errors are listed separately. Partial success is possible — some events may be created while others fail.

---

### update_event

Update an existing event's properties by UID.

Only provided fields are updated; omitted fields are left unchanged. To clear a text field (location, notes, url), pass an empty string "".

Use get_events first to find the event's UID and calendar_name.

For recurring events: use occurrence_date to target a specific occurrence, and span to control whether the change affects just this occurrence or the series.

**Parameters:**
- `calendar_name` (str, required): Exact name of the calendar containing the event
- `event_uid` (str, required): UID of the event to update (from get_events results)
- `summary` (str | None, optional, default: None): New event title
- `start_date` (str | None, optional, default: None): New start date/time in ISO 8601 format
- `end_date` (str | None, optional, default: None): New end date/time in ISO 8601 format
- `location` (str | None, optional, default: None): New location, or "" to clear
- `notes` (str | None, optional, default: None): New notes, or "" to clear
- `url` (str | None, optional, default: None): New URL, or "" to clear
- `allday_event` (bool | None, optional, default: None): New all-day status
- `alert_minutes` (str, optional, default: ""): Comma-separated minutes before event to alert (e.g., "15,60"), or "none" to clear all alerts
- `availability` (str | None, optional, default: None): Event availability: "free", "busy", or "tentative"
- `timezone` (str, optional, default: ""): IANA timezone for interpreting start/end times (e.g., "America/Los_Angeles", "US/Eastern"). When provided, times are interpreted in that timezone instead of the system's local timezone.
- `recurrence_rule` (str | None, optional, default: None): iCalendar RRULE string to set/change recurrence (e.g., "FREQ=WEEKLY;BYDAY=MO,WE,FR"), or "" to remove recurrence
- `occurrence_date` (str, optional, default: ""): For recurring events, the occurrence_date from get_events to target a specific occurrence
- `span` (str, optional, default: "this_event"): "this_event" to update one occurrence, "future_events" to update this and all future occurrences

**Returns:** Confirmation with the event UID and list of updated fields. Note: when rescheduling a single occurrence of a recurring event (changing dates with span="this_event"), a new standalone event is created — the returned UID may differ from the original.

---

### update_events

Update multiple events in a single batch operation.

More efficient than calling update_event multiple times. All events must be on the same calendar.

**Parameters:**
- `calendar_name` (str, required): Exact name of the calendar containing the events
- `updates` (str, required): JSON array of update objects. Each object must have "uid" (required) and at least one field to update: summary, start (ISO 8601), end (ISO 8601), location, notes, url, allday (bool), alerts (list of minutes), availability ("free"/"busy"/"tentative"), timezone (IANA identifier), recurrence (RRULE string), clear_location (bool), clear_notes (bool), clear_url (bool), clear_alerts (bool), clear_recurrence (bool)

**Returns:** Summary of updated events, each with title and list of changed fields. Any per-event errors are listed separately. Partial success is possible.

---

### get_events

Get events from a calendar within a date range.

Returns all events in the specified calendar that overlap with the given date range. Use get_calendars first to find available calendar names.

**Parameters:**
- `calendar_name` (str, required): Exact name of the calendar to query (use get_calendars to find available names)
- `start_date` (str, required): Start of date range in ISO 8601 format (e.g., "2026-03-15" or "2026-03-15T00:00:00")
- `end_date` (str, required): End of date range in ISO 8601 format (must be after start_date)

**Returns:** Each event includes: uid, summary, start_date, end_date, allday_event, location, notes, url, status, calendar_name, availability. For recurring events: is_recurring, recurrence_rule, occurrence_date, is_detached. If alerts are set: alerts (list with minutes_before for each). If attendees exist: attendees (list with name, email, role, status for each). `uid` and `calendar_name` identify the event for update_event and delete_events. For recurring events, also use `occurrence_date` to target a specific occurrence.

---

### search_events

Search events by text across one or all calendars.

Searches event summaries, notes, and locations with case-insensitive matching. If no calendar is specified, searches all calendars. If no date range is specified, searches from 1 month ago to 6 months from now.

**Parameters:**
- `query` (str, required): Text to search for in event titles, notes, and locations
- `calendar_name` (str, optional, default: ""): Calendar to search (searches all calendars if empty)
- `start_date` (str, optional, default: ""): Start of date range in ISO 8601 format
- `end_date` (str, optional, default: ""): End of date range in ISO 8601 format

**Returns:** Matching events with the same fields as get_events. Returns events whose summary, notes, or location contain the query text (case-insensitive).

---

### get_availability

Find free time slots across one or more calendars.

Queries all specified calendars, merges busy periods, and returns available (free) time slots within the date range. Useful for scheduling.

Use get_calendars first to find available calendar names.

**Parameters:**
- `calendar_names` (list[str], required): List of calendar names to check for combined availability
- `start_date` (str, required): Start of range in ISO 8601 format (e.g., "2026-03-15T09:00:00")
- `end_date` (str, required): End of range in ISO 8601 format (e.g., "2026-03-15T17:00:00")
- `min_duration_minutes` (int | None, optional, default: None): Only return slots of at least this many minutes (e.g., 45)
- `working_hours_start` (str | None, optional, default: None): Start of working hours as HH:MM (e.g., "09:00")
- `working_hours_end` (str | None, optional, default: None): End of working hours as HH:MM (e.g., "17:00")

**Returns:** Each free slot includes: start_date, end_date, duration (formatted as hours and minutes). Slots are gaps between busy periods across all specified calendars. Overlapping events are merged. Returns "No free time" if the entire range is busy.

---

### get_conflicts

Detect double-bookings and overlapping events across calendars.

Finds all pairs of events that overlap in time within the date range. Useful for checking if you have scheduling conflicts before adding new events.

Use get_calendars first to find available calendar names.

**Parameters:**
- `calendar_names` (list[str], required): List of calendar names to check for conflicts
- `start_date` (str, required): Start of range in ISO 8601 format (e.g., "2026-03-15T00:00:00")
- `end_date` (str, required): End of range in ISO 8601 format (e.g., "2026-03-22T00:00:00")

**Returns:** Each conflict includes two overlapping events with their UIDs, summaries, times, and calendar names, plus the overlap window and duration in minutes. Events marked as "free" availability are excluded. Returns "No conflicts" if no overlapping events found.

---

### delete_events

Delete one or more events from a calendar by UID.

Accepts a single UID or a list of UIDs for batch deletion. Events that don't exist are reported but don't cause the entire operation to fail.

Use get_events first to find the event UID(s) and calendar_name.

For recurring events: use occurrence_date to target a specific occurrence, and span to control deletion scope. Without occurrence_date, deletes the base event (which may affect the entire series).

**Parameters:**
- `calendar_name` (str, required): Exact name of the calendar containing the event(s)
- `event_uid` (str | list[str], required): UID of a single event (str) or list of UIDs to delete
- `span` (str, optional, default: "this_event"): "this_event" to delete one occurrence, "future_events" to delete the series from this point onward
- `occurrence_date` (str, optional, default: ""): For recurring events, the occurrence_date from get_events to target a specific occurrence

**Returns:** Count of deleted events. Any UIDs not found are listed separately — these don't cause the operation to fail.
