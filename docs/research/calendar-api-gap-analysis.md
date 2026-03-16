# Apple Calendar API Gap Analysis

**Date:** 2026-03-15
**macOS:** Darwin 25.3.0
**Calendar.app:** v16.0

## Research Method

Tested AppleScript and JXA (JavaScript for Automation) against a live Calendar.app instance with 15 calendars and 5600+ events. All tests were read-only.

Note: `sdef /Applications/Calendar.app` requires full Xcode (not just Command Line Tools). No SDEF file found in the app bundle. Research conducted via empirical AppleScript/JXA testing.

---

## Calendar Object

### Accessible Properties

| Property | Batch Access | Individual Access | Notes |
|----------|-------------|-------------------|-------|
| `name` | ✅ `name of every calendar` | ✅ | Names are NOT unique (two "Family" calendars from different accounts) |
| `writable` | ✅ `writable of every calendar` | ✅ | `false` for subscribed/read-only calendars (Holidays, Birthdays, Siri Suggestions, TripIt, MedHub) |
| `description` | ✅ `description of every calendar` | ✅ | Often contains account email or service identifier |
| `color` | ✅ `color of every calendar` | ✅ | AppleScript: 16-bit RGB integers (3 values per calendar). JXA: 0-1 float RGB values |

### Inaccessible Properties

| Property | Error | Impact |
|----------|-------|--------|
| `uid` | AppleEvent handler failed (-10000) | **Critical:** Cannot uniquely identify calendars. Must use name-based lookup. |
| `id` | AppleEvent handler failed (-10000) | Same as uid |
| `properties` | AppleEvent handler failed (-10000) | Cannot get all properties at once. Must fetch individually. |

### Workaround for Calendar Identification

Since UIDs are inaccessible, calendars must be identified by name. For duplicate names, the `description` field (which often contains account info) can disambiguate. The API should document this limitation clearly.

---

## Event Object

### Accessible Properties (tested on individual events)

| Property | Access | Type/Format | Notes |
|----------|--------|-------------|-------|
| `summary` | ✅ | string | Event title |
| `start date` | ✅ | date → `"Monday, April 3, 2023 at 10:35:00 AM"` | Locale-dependent format |
| `end date` | ✅ | date → same format | |
| `uid` | ✅ | string UUID `"3290DD8F-17E9-4DCC-B5FA-764655253E7A"` | **Works for events** (unlike calendars) |
| `allday event` | ✅ | boolean | |
| `description` | ✅ | string | Event notes/body |
| `location` | ✅ | string | |
| `url` | ✅ | string or `missing value` | |
| `status` | ✅ | enum: `none`, `confirmed`, `tentative`, `cancelled` | |
| `recurrence` | ✅ | string (RRULE) or `missing value` | iCalendar RRULE format |
| `excluded dates` | ✅ | list of dates or empty | For recurring event exceptions |
| `stamp date` | ✅ | date | Last modified timestamp |
| `sequence` | ✅ | integer (0-based) | iCalendar sequence number |
| `attendees` | ✅ (element) | list of attendee objects | Can query count; individual properties need testing |

### Date Format

AppleScript returns: `"Monday, April 3, 2023 at 10:35:00 AM"`

This differs from OmniFocus format (`"March 5, 2026 5:00:00 PM"`) — includes day name and uses "at" separator. The date format is **locale-dependent** and may vary by system settings.

JXA returns native JavaScript Date objects which support `.toISOString()` — but JXA has the same property access failures on calendars.

---

## Performance

### Critical Finding: `whose` Clause Timeout

```applescript
-- TIMED OUT on calendar with 5602 events:
every event of cal whose start date ≥ today and start date < (today + 30 * days)
```

This is a blocking issue for `get_events`. Potential strategies:
1. **Narrower date windows** — test with shorter ranges
2. **Batch property access** — `summary of events 1 thru N of cal` (tested: works for first 3)
3. **JXA with index-based access** — timed out on first event of large collection
4. **EventKit via PyObjC** — alternative to AppleScript, direct framework access (future investigation)

### What Works

- `count of events of cal` — fast, returns 5602 instantly
- `name of every calendar` — fast, all 15 calendars
- `event N of cal` — direct index access works for specific events
- Individual property access on specific events — fast

### IPC Cost Estimate

Per OmniFocus benchmarks: ~17ms per property read. Calendar likely similar. With 10 properties per event × 100 events = ~17 seconds. Minimizing property reads is critical.

### Solution: EventKit via Swift Helper

The `whose` clause timeout was resolved by implementing a Swift helper (`src/apple_calendar_mcp/swift/get_events.swift`) that uses EventKit's `EKEventStore` with native predicate-based queries. This provides sub-second reads on any calendar size.

### Benchmarks (2026-03-16, 16 calendars, Work calendar: 1376 events)

| Operation | Method | Time | Notes |
|-----------|--------|------|-------|
| `get_calendars` | AppleScript (batch) | ~6.4s | Slow — 16 calendars, batch property reads |
| `get_events` (1 month) | EventKit/Swift | ~0.4s | Fast — native predicate filtering |
| `get_events` (1 year) | EventKit/Swift | ~0.5s | Scales well |
| `get_events` (10 years, 1376 events) | EventKit/Swift | ~0.8s | Sub-second even for large ranges |
| `get_availability` (1 month) | EventKit + Python | ~0.4s | Inherits get_events performance |
| `get_availability` (1 year) | EventKit + Python | ~0.5s | |
| `create_event` | AppleScript | ~1.7s | Single event, acceptable |
| `update_event` | AppleScript (`whose uid`) | ~2.6s | UID lookup + property set |
| `delete_events` (single) | AppleScript (`whose uid`) | ~2.4s | Single UID lookup |
| `delete_events` (batch, 5) | AppleScript (`whose uid` × 5) | ~14.5s | Linear scaling, N separate invocations |

**Key observations:**
- **Read operations (EventKit)** are sub-second regardless of calendar size
- **Write operations (AppleScript)** are 1–3s per operation due to IPC overhead
- **Batch delete scales linearly** — each UID requires a separate AppleScript invocation
- **get_calendars is surprisingly slow** at ~6.4s for AppleScript batch property reads
- Write performance is acceptable for typical single-event use (create, update, delete one)
- Batch delete of 10+ events may feel slow; consider EventKit migration if this becomes a common use case

---

## Write Operations

All write operations implemented and tested via AppleScript:

| Operation | AppleScript Command | Status | Timing |
|-----------|-------------------|--------|--------|
| Create calendar | `make new calendar with properties {name:"X"}` | ✅ Implemented (test setup) | <1s |
| Create event | `make new event at end of events of cal with properties {...}` | ✅ Implemented | ~1.7s |
| Update event | `set summary of evt to "X"` (via `whose uid`) | ✅ Implemented | ~2.6s |
| Delete event | `delete evt` (via `whose uid`) | ✅ Implemented | ~2.4s |
| Delete calendar | `delete cal` | ✅ Implemented (test teardown) | <1s |

---

## Feature Priority Tiers

### P1 — Core CRUD (v0.1.0)

| Feature | UI Available | AppleScript | Status |
|---------|-------------|-------------|--------|
| List calendars | ✅ | ✅ (batch properties) | Ready to implement |
| Create event | ✅ | Likely (untested) | Needs test calendar |
| Read events | ✅ | ✅ (individual), ❌ (`whose` timeout) | Needs filtering strategy |
| Update event | ✅ | Likely (untested) | Needs test calendar |
| Delete event | ✅ | Likely (untested) | Needs test calendar |

### P2 — Filters & Queries (v0.2.0)

| Feature | UI Available | AppleScript | Status |
|---------|-------------|-------------|--------|
| Filter by date range | ✅ | ❌ (`whose` timeout) | Needs alternative strategy |
| Filter by calendar | ✅ | ✅ (access events of specific calendar) | Ready |
| Search by text | ✅ (Spotlight) | Unknown | Needs testing |
| Free/busy lookup | ✅ (availability) | Unknown | Needs testing |

### P3 — Advanced (v0.3.0)

| Feature | UI Available | AppleScript | Status |
|---------|-------------|-------------|--------|
| Recurring events | ✅ | ✅ Read + create with RRULE. See Recurring Events section. | Tested 2026-03-16 |
| Attendees | ✅ | Partial (count works) | Individual attendee properties untested |
| Alerts/reminders | ✅ | Unknown | Needs testing |
| Travel time | ✅ | Unknown | Needs testing |
| Calendar sharing | ✅ | Unknown | Likely not available |

---

## Recurring Events (tested 2026-03-16)

### Creating Recurring Events

AppleScript supports setting recurrence with RRULE syntax at creation time:

```applescript
make new event at end of events with properties {summary:"Weekly Standup", start date:date "July 01, 2026 09:00:00 AM", end date:date "July 01, 2026 09:30:00 AM", recurrence:"FREQ=WEEKLY;BYDAY=MO,WE,FR"}
```

Reading back: `recurrence of event` returns `"FREQ=WEEKLY;INTERVAL=1;BYDAY=MO,WE,FR"` (Calendar normalizes by adding `INTERVAL=1`).

### Occurrence UIDs

**All occurrences of a recurring event share the same UID.** Querying via EventKit returns one event object per occurrence, each with the same `calendarItemIdentifier`. Occurrences are distinguished by their `occurrenceDate` / `startDate`.

This means **UID alone is insufficient to target a specific occurrence** — you need UID + date.

### Modification Behavior (AppleScript)

**Modifying the series event modifies ALL occurrences.** When using `whose uid is "..."` to find a recurring event and setting a property (e.g., `set summary`), all occurrences are updated. AppleScript does not offer a way to modify a single occurrence through `whose uid`.

**Deleting via `item N of matchingEvents` removes a single occurrence.** When `whose uid` returns multiple items (one per occurrence), deleting `item 1` removes only that occurrence (adds it to excluded dates). However, `delete (every event whose uid is ...)` does NOT delete the entire series — it only removes visible occurrences, and the series regenerates new ones. To fully remove a recurring series, delete the calendar and recreate it, or use EventKit's `remove(_:span:)` with `.futureEvents`.

### EventKit Properties

Each occurrence exposes:
- `hasRecurrenceRules`: `true` — the occurrence belongs to a recurring series
- `isDetached`: `false` — not individually modified (would be `true` for detached occurrences)
- `occurrenceDate`: the specific date of this occurrence (ISO 8601)
- `recurrenceRules`: array containing the RRULE (e.g., `FREQ=WEEKLY;INTERVAL=1;BYDAY=MO,WE,FR`)

### Implications for API Design

1. **Read support**: Extend Swift helper to return `recurrence_rule`, `is_recurring`, and `occurrence_date` fields
2. **Create support**: Add optional `recurrence_rule` parameter (RRULE string) to `create_event`
3. **Update behavior**: Updating by UID modifies the entire series. To modify a single occurrence, EventKit's `save(_:span:)` with `.thisEvent` span is needed (not available via AppleScript)
4. **Delete behavior**: Current `delete_events` with `whose uid` + `delete` removes one occurrence. Deleting all matching events removes the series. Consider adding a `delete_series` flag.
5. **Occurrence identification**: Need UID + occurrence_date to uniquely identify an occurrence

---

## Open Questions

1. ~~**Event filtering on large calendars:**~~ Solved — EventKit via Swift helper provides sub-second queries on any calendar size.
2. ~~**Recurring event modification:**~~ Answered — AppleScript modification via `whose uid` affects the entire series. Single-occurrence modification requires EventKit's `.thisEvent` span. See Recurring Events section.
3. **Attendee properties:** What fields are available on attendee objects?
4. ~~**Calendar creation:**~~ Answered — `make new calendar with properties {name:"X"}` works. Used in test setup.
5. **Alert/reminder access:** Can we read/set event alerts via AppleScript?
6. ~~**EventKit alternative:**~~ Partially answered — EventKit via Swift helper is used for reads. Write migration depends on Claude Desktop usability testing (#33).
