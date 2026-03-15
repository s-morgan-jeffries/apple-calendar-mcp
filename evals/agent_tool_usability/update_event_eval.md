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
