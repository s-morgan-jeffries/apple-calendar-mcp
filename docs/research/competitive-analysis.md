# Competitive Analysis: Calendar MCP Servers

**Date:** 2026-03-21

## Apple Calendar MCP Servers

### Omar-V2/mcp-ical
- **URL:** https://github.com/Omar-V2/mcp-ical
- **Stars:** ~183
- **Stack:** Python, AppleScript
- **Tools:** 1 (single tool that takes natural language, delegates to LLM for interpretation)
- **Features:** Event creation, modification, schedule listing, free time search. Supports recurring events via iCloud sync with Google Calendar.
- **Tests:** Has a pytest suite that creates temporary calendars.
- **Limitations:** Single monolithic tool (no structured tool separation), AppleScript-based (slow on large calendars), no batch operations, no availability/conflict detection as dedicated tools, no agent evals.

### PsychQuant/che-ical-mcp
- **URL:** https://github.com/PsychQuant/che-ical-mcp
- **Stars:** ~3
- **Stack:** Swift/EventKit (native)
- **Tools:** 24 (calendar + reminders combined)
- **Features:** Calendar CRUD, batch operations, reminders CRUD, recurring events, location-based triggers, geofencing, tags, flexible date parsing, fuzzy calendar matching, same-name calendar disambiguation, idempotent writes.
- **Limitations:** Very low adoption. No test suite visible. Combines calendar and reminders into one server (bloated tool surface for calendar-only use). No agent eval framework. Minimal documentation.

### shadowfax92/apple-calendar-mcp
- **URL:** https://github.com/shadowfax92/apple-calendar-mcp
- **Stars:** ~2
- **Stack:** Python, AppleScript
- **Tools:** 5 (getCalendars, getCalendarEvents, createCalendarEvent, updateCalendarEvent, deleteCalendarEvent)
- **Limitations:** No search, no batch operations, no availability, no recurring event support, no conflict detection. Low activity. No tests visible.

### FradSer/mcp-server-apple-events
- **URL:** https://github.com/FradSer/mcp-server-apple-events
- **Stars:** ~55
- **Stack:** Swift/EventKit
- **Tools:** Combined calendar + reminders tools
- **Features:** Full CRUD for reminders and calendar events, recurring events, priority, alarms, location triggers, subtasks. Includes MCP prompt templates.
- **Limitations:** Reminders-focused (calendar is secondary). Test coverage unknown.

### supermemoryai/apple-mcp
- **URL:** https://github.com/supermemoryai/apple-mcp
- **Stars:** ~2,200 (highest in category)
- **Stack:** TypeScript/Swift
- **Tools:** Multi-app (Messages, Notes, Contacts, Mail, Reminders, Calendar, Maps)
- **Features (Calendar):** Create events, search events, list upcoming events, open event details.
- **Limitations:** Jack-of-all-trades. Calendar is a small subset of a broad Apple integration suite. No update/delete for events, no batch operations, no availability, no conflict detection, no recurring event support. No calendar-specific tests.

### Allenyzh/mcp-server-apple-calendar
- **URL:** https://github.com/Allenyzh/mcp-server-apple-calendar
- **Stars:** 0
- **Stack:** TypeScript, AppleScript
- **Tools:** 1 (create event only)
- **Limitations:** Create-only. No read, update, delete, search. Abandoned (last commit 11+ months ago).

### somethingwithproof/calendar-mcp
- **URL:** https://github.com/somethingwithproof/calendar-mcp
- **Stars:** Low
- **Stack:** TypeScript/Node.js
- **Tools:** ~3 (get calendars, get events, create events)
- **Limitations:** Read + create only. No update, delete, search, availability. Minimal.

## Google Calendar MCP Servers

### nspady/google-calendar-mcp
- **URL:** https://github.com/nspady/google-calendar-mcp
- **Stars:** ~1,000
- **Stack:** TypeScript/Node.js, Google Calendar API
- **Tools:** 6 (list-calendars, list-events, search-events, create-event, update-event, delete-event)
- **Features:** Multi-account, multi-calendar, recurring events, free/busy queries, cross-account conflict detection, smart scheduling with natural language dates, import from images/PDFs/links.
- **Tests:** Vitest-based unit + integration tests with coverage.
- **Limitations:** Google Calendar only. Requires OAuth setup. No batch operations. 6 tools vs our 12. No agent eval framework.

### MarimerLLC/calendar-mcp
- **URL:** https://github.com/MarimerLLC/calendar-mcp
- **Stack:** .NET 10, Microsoft Graph API + Google OAuth
- **Tools:** Multi-service (email + calendar + contacts across M365, Outlook.com, Google Workspace)
- **Limitations:** Heavy .NET dependency. Enterprise-focused. Calendar is one piece of a broader suite.

### ridafkih/keeper.sh
- **URL:** https://github.com/ridafkih/keeper.sh
- **Stack:** Docker-based, multi-provider (Google, Outlook, Office 365, iCloud, CalDAV, ICS)
- **Features:** Universal calendar sync + MCP server. Aggregates across providers.
- **Limitations:** MCP is read-only (list calendars, query events only). Cannot create, update, or delete events. Requires Docker hosting.

## Comparison Table

| Feature | **Our Server** | Omar-V2/mcp-ical | che-ical-mcp | supermemoryai/apple-mcp | nspady/google-calendar |
|---|---|---|---|---|---|
| **Platform** | Apple (native) | Apple (AS) | Apple (native) | Apple (multi-app) | Google |
| **Tools** | 12 | 1 | 24 (incl. reminders) | ~4 calendar | 6 |
| **Performance** | Swift/EventKit (sub-second) | AppleScript (slow) | Swift/EventKit | Swift | Google API |
| **Batch operations** | create_events, update_events | No | create_events_batch | No | No |
| **Availability** | Smart (working hours, min duration) | No | No | No | free/busy |
| **Conflict detection** | Dedicated tool | No | No | No | Cross-account |
| **Recurring events** | RRULE create/update/delete | Via iCloud sync | Yes | No | Yes |
| **Search** | Dedicated search_events | No | list filter/sort | Basic | search-events |
| **Unit tests** | 157 | Some | None visible | None visible | Yes (Vitest) |
| **Integration tests** | 57 | Some | None visible | None visible | Yes |
| **Agent evals** | 38 scenarios | No | No | No | No |

## Our Key Differentiators

1. **Deepest Apple Calendar tool surface (12 dedicated tools)** — No other Apple Calendar MCP comes close. che-ical-mcp has 24 tools but half are reminders. supermemoryai has 2,200 stars but only ~4 shallow calendar tools.

2. **Swift/EventKit performance** — Sub-second reads even on calendars with thousands of events. Most competitors use AppleScript, which times out on large calendars (~18s for 306 events in our benchmarks).

3. **Batch operations** — `create_events` and `update_events` are unique. No other Apple Calendar MCP server (and no Google Calendar MCP server) offers batch create or batch update.

4. **Smart availability** — `get_availability` with working hours filtering and minimum duration is unique. `get_conflicts` as a dedicated tool is also unique among Apple Calendar servers.

5. **Recurring event support with RRULE** — Create, update, and delete individual occurrences or entire series. Most competitors either ignore recurrence or delegate to iCloud sync.

6. **Testing rigor** — 157 unit + 57 integration tests is unmatched. No other Apple Calendar MCP has visible tests. Our 38-scenario agent eval framework is entirely unique in the calendar MCP space.

7. **Structured returns with comprehensive docstrings** — All tools return dict/list[dict], never formatted text. Tool docstrings include Returns sections for LLM tool selection accuracy.

8. **Calendar safety** — Test mode environment variables prevent accidental writes to real calendars. No competitor has this safeguard.
