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

---

## Write Operations (not yet tested)

These need testing against a test calendar:

| Operation | AppleScript Command | Priority |
|-----------|-------------------|----------|
| Create calendar | `make new calendar with properties {name:"X"}` | P1 |
| Create event | `make new event at end of events of cal with properties {summary:"X", start date:D, end date:D}` | P1 |
| Update event | `set summary of evt to "X"` | P1 |
| Delete event | `delete evt` | P1 |
| Delete calendar | `delete cal` | P2 |

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
| Recurring events | ✅ | Partial (recurrence property readable) | Modification behavior unknown |
| Attendees | ✅ | Partial (count works) | Individual attendee properties untested |
| Alerts/reminders | ✅ | Unknown | Needs testing |
| Travel time | ✅ | Unknown | Needs testing |
| Calendar sharing | ✅ | Unknown | Likely not available |

---

## Open Questions

1. **Event filtering on large calendars:** What's the largest date range that doesn't timeout? Is there a pagination strategy?
2. **Recurring event modification:** Does modifying one instance affect the series? Can we target a specific occurrence?
3. **Attendee properties:** What fields are available on attendee objects?
4. **Calendar creation:** Does `make new calendar` work? What properties can be set?
5. **Alert/reminder access:** Can we read/set event alerts via AppleScript?
6. **EventKit alternative:** Would PyObjC + EventKit provide better performance and more capabilities than AppleScript?
