# Blind Agent Eval: get_calendars

## Purpose
Verify that an agent can figure out how to list calendars using only the MCP tool descriptions.

## Setup
Give an agent access to the apple-calendar-mcp tools with NO additional instructions beyond the MCP server's `instructions` block and tool docstrings.

## Scenarios

### Scenario 1: List all calendars
**Prompt:** "What calendars do I have?"
**Expected:** Agent calls `get_calendars()` with no arguments.
**Pass criteria:** Agent calls the correct tool and presents the results.

### Scenario 2: Find writable calendars
**Prompt:** "Which calendars can I add events to?"
**Expected:** Agent calls `get_calendars()`, then filters results by `writable: true` / `Access: read-write`.
**Pass criteria:** Agent correctly identifies writable vs read-only calendars.

### Scenario 3: Disambiguate duplicate names
**Prompt:** "I have two calendars called 'Family'. Which is which?"
**Expected:** Agent calls `get_calendars()` and uses the `description` field to distinguish them.
**Pass criteria:** Agent references descriptions or account info to differentiate.

## Scoring
- 3/3 pass: Tool descriptions are clear
- 2/3 pass: Minor description improvements needed
- 1/3 or fewer: Rewrite descriptions before release

## Results
_Run these scenarios before each release that changes tool descriptions._
