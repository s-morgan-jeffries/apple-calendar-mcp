# Blind Eval: update_event Tool Description

Test whether an agent can correctly use the `update_event` tool from its description alone.

## Scenario 1: Simple field update

**User prompt:** "Change the title of my 2pm meeting today to 'Project Review'"

**Expected agent behavior:**
1. Call `get_events` to find today's events
2. Identify the 2pm event and note its UID and calendar_name
3. Call `update_event` with `calendar_name`, `event_uid`, and `summary="Project Review"`

**Watch for:**
- Agent uses the UID from get_events (not fabricated)
- Agent passes the correct calendar_name from the event
- Agent only sets summary, not other fields

## Scenario 2: Update location

**User prompt:** "Move my 'Team Standup' event to Conference Room B"

**Expected agent behavior:**
1. Call `get_events` to find the event by summary
2. Call `update_event` with `location="Conference Room B"`

**Watch for:**
- Agent correctly interprets "move" as updating location, not dates
- Agent does not modify start_date or end_date

## Scenario 3: Clear a field

**User prompt:** "Remove the location from my dentist appointment"

**Expected agent behavior:**
1. Call `get_events` to find the dentist appointment
2. Call `update_event` with `location=""`

**Watch for:**
- Agent passes empty string "" to clear the field (not None/omit)
- Agent understands the distinction between clearing and not modifying

## Scenario 4: Reschedule an event

**User prompt:** "Move my 10am meeting to 3pm today"

**Expected agent behavior:**
1. Call `get_events` to find the 10am event
2. Call `update_event` with both `start_date` and `end_date` adjusted by 5 hours

**Watch for:**
- Agent updates BOTH start_date and end_date (not just start)
- Agent preserves the event duration
- Agent uses ISO 8601 format for dates

## Scenario 5: Make a one-off event recurring

**User prompt:** "Make my 'Team Sync' event on Monday repeat every week"

**Expected agent behavior:**
1. Call `get_events` to find the Team Sync event
2. Call `update_event` with `recurrence_rule="FREQ=WEEKLY"` (or `FREQ=WEEKLY;BYDAY=MO`)

**Watch for:**
- Agent uses `recurrence_rule` parameter (not trying to delete and recreate)
- Agent produces a valid iCalendar RRULE string
- Agent does not modify other fields

## Scenario 6: Change recurrence pattern

**User prompt:** "My 'Status Update' meeting currently repeats weekly. Change it to every two weeks instead."

**Expected agent behavior:**
1. Call `get_events` to find the Status Update event
2. Call `update_event` with `recurrence_rule="FREQ=WEEKLY;INTERVAL=2"`

**Watch for:**
- Agent uses `recurrence_rule` to change the pattern (not delete/recreate)
- Agent includes INTERVAL=2 in the RRULE

## Scenario 7: Remove recurrence

**User prompt:** "Stop my 'Daily Standup' from repeating. Just keep the next occurrence."

**Expected agent behavior:**
1. Call `get_events` to find the Daily Standup event
2. Call `update_event` with `recurrence_rule=""`

**Watch for:**
- Agent passes empty string `""` to clear recurrence (not None/omit)
- Agent understands this converts recurring to one-off

## Scenario 8: Add complex recurrence to existing event

**User prompt:** "Make my 'Quarterly Review' event repeat every 3 months on the 2nd Thursday until the end of 2027."

**Expected agent behavior:**
1. Call `get_events` to find the Quarterly Review event
2. Call `update_event` with `recurrence_rule="FREQ=MONTHLY;INTERVAL=3;BYDAY=2TH;UNTIL=20271231"` or similar

**Watch for:**
- Agent produces RRULE with FREQ=MONTHLY, INTERVAL=3, BYDAY=2TH, and UNTIL
- Agent uses correct nth weekday syntax (2TH, not just TH)
