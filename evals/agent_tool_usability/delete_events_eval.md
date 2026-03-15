# Blind Eval: delete_events Tool Description

Test whether an agent can correctly use the `delete_events` tool from its description alone.

## Scenario 1: Delete a single event by UID

**User prompt:** "Delete the event with UID ABC-123 from my Work calendar."

**Expected agent behavior:**
1. Call `delete_events` with `calendar_name="Work"` and `event_uid="ABC-123"`

**Watch for:**
- Agent passes the UID as a string, not a list
- Agent includes the correct calendar_name

## Scenario 2: Delete multiple events

**User prompt:** "Delete all three of my test events: ABC-123, DEF-456, GHI-789 from Work"

**Expected agent behavior:**
1. Call `delete_events` with `event_uid=["ABC-123", "DEF-456", "GHI-789"]`

**Watch for:**
- Agent passes a list of UIDs in a single call (not three separate calls)
- Agent uses the list form of event_uid

## Scenario 3: Find and delete an event

**User prompt:** "Cancel my dentist appointment next Tuesday"

**Expected agent behavior:**
1. Call `get_events` to find the dentist appointment and note its UID and calendar_name
2. Call `delete_events` with the discovered UID and calendar_name

**Watch for:**
- Agent uses get_events first to find the UID (not fabricated)
- Agent passes the correct calendar_name from the event

## Scenario 4: Handle partial failure

**User prompt:** "Delete events ABC-123 and DEF-456 from my Work calendar"

**Expected agent behavior:**
1. Call `delete_events` with `event_uid=["ABC-123", "DEF-456"]`
2. If result mentions not-found UIDs, inform user which ones weren't found

**Watch for:**
- Agent reports partial success clearly to the user
- Agent does not retry the not-found UIDs
