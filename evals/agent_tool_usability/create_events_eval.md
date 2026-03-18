# Blind Agent Eval: create_events (batch)

## Purpose
Verify that an agent knows when to use `create_events` (batch) vs `create_event` (single), and can format the JSON events array correctly.

## Setup
Give an agent access to the apple-calendar-mcp tools with NO additional instructions beyond the MCP server's `instructions` block and tool docstrings.

## Scenarios

### Scenario 1: Multiple events in one request
**Prompt:** "Add three meetings to my Work calendar: Team Standup Mon 9-9:30am, Design Review Mon 2-3pm, and Sprint Planning Tue 10-11am."
**Expected:** Agent calls `create_events` (not three separate `create_event` calls) with a JSON array of 3 event objects.
**Pass criteria:** Agent uses batch tool, JSON is valid, all 3 events have correct summary/start/end.

### Scenario 2: Single event — should NOT use batch
**Prompt:** "Add a dentist appointment to my Personal calendar on Friday at 2pm for an hour."
**Expected:** Agent calls `create_event` (singular), not `create_events`.
**Pass criteria:** Agent uses the single-event tool for a single event.

### Scenario 3: Conference schedule import
**Prompt:** "Here's a conference schedule for Thursday. Add all of these to Work: Opening Keynote 9-10am, Workshop A 10:15-11:45am at Room 101, Lunch 12-1pm (mark as free), Workshop B 1:15-2:45pm at Room 203, Closing Panel 3-4pm."
**Expected:** Agent calls `create_events` with 5 events, including locations and availability=free for lunch.
**Pass criteria:** JSON array has 5 objects with correct fields. Lunch event has availability "free". Workshop events have locations.

### Scenario 4: Events with mixed features
**Prompt:** "Add to my Work calendar: Weekly Team Sync every Monday 10-11am recurring weekly, a one-time Project Kickoff on Wednesday 2-4pm with a 30-minute alert, and an All-Day Planning Day on Friday."
**Expected:** Agent calls `create_events` with 3 events: one with recurrence, one with alerts, one all-day.
**Pass criteria:** JSON includes recurrence RRULE for first event, alerts=[30] for second, allday=true for third.

### Scenario 5: Timezone-specific batch
**Prompt:** "I'm scheduling meetings with our West Coast team. Add these to Work — all times are Pacific: Sync Call Mon 9am-10am, Follow-Up Tue 2pm-3pm."
**Expected:** Agent calls `create_events` with timezone "America/Los_Angeles" on each event (or asks if all events share the timezone).
**Pass criteria:** Events include timezone field with a valid Pacific timezone identifier.

## Scoring
- 4/5 or 5/5 pass: Tool descriptions are clear
- 3/5 pass: Minor description improvements needed
- 2/5 or fewer: Rewrite descriptions before release

## Results
_Run these scenarios before each release that changes tool descriptions._
