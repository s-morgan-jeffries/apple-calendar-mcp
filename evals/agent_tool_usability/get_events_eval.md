# Blind Eval: get_events Tool Description

Test whether an agent can correctly use the `get_events` tool from its description alone.

## Scenario 1: Basic daily schedule query

**User prompt:** "What's on my Work calendar today?"

**Expected agent behavior:**
1. Call `get_calendars` to confirm "Work" exists
2. Call `get_events` with `calendar_name="Work"`, `start_date="<today>T00:00:00"`, `end_date="<tomorrow>T00:00:00"`
3. Present results in a readable format

**Watch for:**
- Agent uses correct ISO 8601 date format
- Agent queries a single day (not a week or month)
- Agent calls get_calendars first to verify the calendar name

## Scenario 2: Multi-day range query

**User prompt:** "Show me my Personal events for next week (March 16-22)."

**Expected agent behavior:**
1. Call `get_events` with `calendar_name="Personal"`, `start_date="2026-03-16T00:00:00"`, `end_date="2026-03-23T00:00:00"`

**Watch for:**
- Agent sets end_date to the day AFTER the last requested day (exclusive end)
- Agent uses the exact calendar name

## Scenario 3: Disambiguating calendars

**User prompt:** "Do I have anything on my Family calendar this weekend?"

**Expected agent behavior:**
1. Call `get_calendars` — discovers two "Family" calendars
2. Ask user which Family calendar they mean, using description to disambiguate
3. Call `get_events` with the correct calendar name and weekend date range

**Watch for:**
- Agent recognizes duplicate calendar names
- Agent doesn't blindly pick the first one
- Agent asks for clarification
