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

### Scenario 5: Weekly recurring with simple BYDAY
**Prompt:** "Set up a recurring meeting called 'Sprint Planning' every Monday and Wednesday at 2pm for an hour on my Work calendar."
**Expected:** Agent calls `create_event` with `recurrence_rule="FREQ=WEEKLY;BYDAY=MO,WE"`.
**Pass criteria:** Agent produces a valid RRULE with FREQ=WEEKLY and BYDAY containing MO and WE. Start/end dates set correctly for the first occurrence.

### Scenario 6: Monthly nth weekday recurrence
**Prompt:** "Create a recurring event called 'Board Meeting' on the 4th Tuesday of every month at 3pm for 2 hours on my Work calendar."
**Expected:** Agent calls `create_event` with `recurrence_rule="FREQ=MONTHLY;BYDAY=4TU"` or equivalent.
**Pass criteria:** Agent produces an RRULE with `BYDAY=4TU` (or `4TU` somewhere in a valid RRULE). Start date should be the next 4th Tuesday.

### Scenario 7: Complex recurrence with UNTIL
**Prompt:** "I need a weekly team lunch every Friday starting this week until Christmas on my Work calendar. 12pm to 1pm."
**Expected:** Agent calls `create_event` with `recurrence_rule="FREQ=WEEKLY;BYDAY=FR;UNTIL=YYYYMMDD"` where UNTIL is Dec 25 of the current year.
**Pass criteria:** Agent produces a valid RRULE with FREQ=WEEKLY, BYDAY=FR, and an UNTIL date near Dec 25. UNTIL format should be YYYYMMDD or YYYYMMDDTHHMMSS.

### Scenario 8: Last weekday of month
**Prompt:** "Schedule 'Month-End Review' on the last Friday of every month at 4pm for 1 hour on Work, for the next 6 months."
**Expected:** Agent calls `create_event` with `recurrence_rule="FREQ=MONTHLY;BYDAY=-1FR;COUNT=6"` or uses UNTIL.
**Pass criteria:** Agent produces an RRULE with `BYDAY=-1FR` and either COUNT=6 or an appropriate UNTIL date.

### Scenario 9: Every N months
**Prompt:** "Set up a quarterly planning session — every 3 months on the 2nd Wednesday, starting next month, for 3 hours. Put it on Work."
**Expected:** Agent calls `create_event` with `recurrence_rule="FREQ=MONTHLY;INTERVAL=3;BYDAY=2WE"`.
**Pass criteria:** Agent produces an RRULE with FREQ=MONTHLY, INTERVAL=3, and BYDAY=2WE. Start date should be the 2nd Wednesday of next month.

## Scoring
- 8/9 or 9/9 pass: Tool descriptions are clear
- 6-7/9 pass: Minor description improvements needed
- 5/9 or fewer: Rewrite descriptions before release

## Results
_Run these scenarios before each release that changes tool descriptions._
