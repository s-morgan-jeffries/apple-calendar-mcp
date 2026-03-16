# Apple Calendar MCP Server

An MCP server bridging Claude and Apple Calendar via AppleScript and EventKit on macOS.

**Stack:** Python 3.10+, FastMCP, AppleScript (via `osascript`), Swift/EventKit (via `swift`)
**Version:** v0.2.0 | **Tests:** 119 unit, 26 integration | **Coverage:** TBD

## Commands

```bash
make test                  # All tests (~unit, mocked AppleScript)
make test-unit             # Unit tests only
make test-integration      # Real Calendar tests (requires test calendar)
make test-verbose          # Tests with verbose output
./scripts/check_complexity.sh       # Cyclomatic complexity check
./scripts/check_version_sync.sh     # Version consistency across files
./scripts/benchmark_performance.sh [calendar]  # Performance benchmarks (real Calendar.app)
```

**Running the server:** `uv run python -m apple_calendar_mcp.server_fastmcp` or via Claude Desktop config.

## API Surface (6 functions)

- **Calendars:** `get_calendars`
- **Events:** `get_events`, `create_event`, `update_event`, `delete_events`
- **Availability:** `get_availability`

Planned (filed as issues): `update_events`

## Core API Principles

1. **Comprehensive update functions over specialized operations** — no `set_event_title()`, use `update_event(event_id, title=X)`
2. **No field-specific setters or getters** — `update_event` handles all fields, `get_events` handles all filters
3. **Separate single/batch updates** — batch excludes title/notes (require unique values)
4. **Union types for deletes only** — `Union[str, list[str]]` for delete operations, NOT for updates
5. **No upsert pattern** — create and update are always separate
6. **Structured returns** — always `dict` or `list[dict]`, never formatted text strings

## AppleScript Gotchas (Calendar-specific)

**Calendar UIDs inaccessible:** `uid of every calendar` and `id of every calendar` both fail with AppleEvent handler error -10000. Calendars must be identified by name. Duplicate names exist (e.g., two "Family" calendars from different accounts).

**Batch vs individual access:** `name of every calendar` works but `properties of calendar "X"` fails. Use batch property access for calendars.

**Event UIDs differ across APIs:** AppleScript's `uid of event` returns a different identifier than EventKit's `eventIdentifier`. Use EventKit's `calendarItemIdentifier` to get UIDs that match AppleScript. The Swift helper uses `calendarItemIdentifier` for this reason.

**Event UIDs work fine in AppleScript:** Individual event property access works: `uid of event`, `summary of event`, `start date of event`, etc.

**Variable naming conflicts:** Never use variable names that match Calendar properties. If Calendar has a `summary` property, don't use `summary` as a variable name — use `eventSummary`.

**JSON helpers duplicated:** AppleScript has no imports/modules. Every AppleScript block that returns JSON must include its own helper functions. This is intentional.

**Date format:** AppleScript returns dates as `"Monday, April 3, 2023 at 10:35:00 AM"` (locale-dependent, includes day name). The connector handles ISO 8601 conversion.

**Date ordering on updates:** AppleScript rejects `set start date` if the new start is after the current end date (and vice versa). When updating both dates, `update_event` temporarily extends the end date to avoid this constraint.

**String escaping:** Always use `_escape_applescript_string()` for user-provided text. Unescaped quotes break AppleScript blocks silently.

**Performance:** `whose` clause with date filtering timed out on large calendars (5600+ events). AppleScript event reads are fundamentally too slow (~9s/event for index access, ~18s/property-batch for 306 events). `get_events` uses EventKit via Swift helper instead.

## Hybrid Architecture

- **Writes** (create, update, delete): AppleScript via `osascript` — fast for single-event operations
- **Reads** (get_events): Swift/EventKit via `swift` subprocess — native date-range queries, sub-second on any calendar size

The Swift helper at `src/apple_calendar_mcp/swift/get_events.swift` uses `EKEventStore` for fast predicate-based queries. First run triggers a macOS calendar access permission dialog.

## Calendar Safety

Destructive operations require `CALENDAR_TEST_MODE=true` and `CALENDAR_TEST_NAME=MCP-Test-Calendar` environment variables. Each destructive operation verifies the target calendar name before proceeding.

## Testing Requirements

| Type | When Required | How |
|------|--------------|-----|
| Unit tests | Every code change | `make test-unit` |
| Integration tests | New/modified AppleScript operations | `make test-integration` (requires test calendar) |

**Hard rule:** If you wrote or modified an AppleScript string in the connector, integration tests must cover that operation before merge. Unit tests mock `run_applescript()` and `run_swift_helper()` and cannot catch AppleScript/Swift errors.

## Branch Convention

`{type}/issue-{num}-{description}` — e.g., `feature/issue-1-get-calendars`, `fix/issue-5-date-parsing`

CHANGELOG.md is only updated on release branches, never on feature branches.

## Release Workflow

1. Run all tests: `make test` + `make test-integration`
2. Run blind evals if tool descriptions changed (`evals/agent_tool_usability/`)
3. Bump version in `pyproject.toml` and `.claude/CLAUDE.md`
4. Run `./scripts/check_version_sync.sh`
5. Update CHANGELOG.md (release branches only)
6. Tag: `git tag vX.Y.Z` and push

## Key Files

- `src/apple_calendar_mcp/calendar_connector.py` — Core client (AppleScript + Swift helpers)
- `src/apple_calendar_mcp/server_fastmcp.py` — FastMCP server wrapping the connector
- `src/apple_calendar_mcp/swift/get_events.swift` — EventKit-based event query (fast reads)
- `docs/research/calendar-api-gap-analysis.md` — What's possible, what's not
