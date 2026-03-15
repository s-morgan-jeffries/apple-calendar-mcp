# Blind Agent Eval: create_event

## Purpose
Verify that an agent can figure out how to create calendar events using only the MCP tool descriptions.

## Setup
Give an agent access to the apple-calendar-mcp tools with NO additional instructions beyond the MCP server's `instructions` block and tool docstrings.

## Scenarios

### Scenario 1: Create a basic timed event
**Prompt:** "Add a meeting called 'Team Standup' tomorrow at 10am for 30 minutes on my Work calendar."
**Expected:** Agent calls `get_calendars()` first to verify "Work" exists, then calls `create_event(calendar_name="Work", summary="Team Standup", start_date="..T10:00:00", end_date="..T10:30:00")`.
**Pass criteria:** Agent uses correct calendar name, ISO 8601 dates, and presents the UID in the response.

### Scenario 2: Create an all-day event
**Prompt:** "Block off next Friday as a holiday on my Personal calendar."
**Expected:** Agent calls `create_event(calendar_name="Personal", summary="Holiday", start_date="YYYY-MM-DD", end_date="YYYY-MM-DD+1", allday_event=True)`.
**Pass criteria:** Agent sets `allday_event=True` and uses date-only format. End date is the day after start date.

### Scenario 3: Create an event with all optional fields
**Prompt:** "Create a lunch meeting on my Work calendar next Tuesday at noon for an hour at 'Café Roma', with a note 'Discuss Q3 roadmap' and link to https://docs.example.com/q3."
**Expected:** Agent calls `create_event` with summary, start/end dates, location, description, and url all populated.
**Pass criteria:** Agent populates location, description, and url fields correctly.

### Scenario 4: Create event on ambiguous calendar
**Prompt:** "Add a birthday party on Saturday to my Family calendar."
**Expected:** Agent calls `get_calendars()` first. If multiple "Family" calendars exist, agent asks for clarification or uses description to disambiguate.
**Pass criteria:** Agent doesn't blindly pick one of the duplicate calendars — it either asks or explains the ambiguity.

## Scoring
- 4/4 pass: Tool descriptions are clear
- 3/4 pass: Minor description improvements needed
- 2/4 or fewer: Rewrite descriptions before release

## Results
_Run these scenarios before each release that changes tool descriptions._
