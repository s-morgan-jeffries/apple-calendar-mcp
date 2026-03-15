# Apple Calendar MCP Server

An MCP server bridging Claude and Apple Calendar via AppleScript on macOS.

**Stack:** Python 3.10+, FastMCP, AppleScript (via `osascript`)
**Version:** v0.1.0 | **Tests:** TBD | **Coverage:** TBD

## Commands

```bash
make test                  # All tests (~unit, mocked AppleScript)
make test-unit             # Unit tests only
make test-integration      # Real Calendar tests (requires test calendar)
make test-verbose          # Tests with verbose output
./scripts/check_complexity.sh       # Cyclomatic complexity check
./scripts/check_version_sync.sh     # Version consistency across files
```

**Running the server:** `uv run python -m apple_calendar_mcp.server_fastmcp` or via Claude Desktop config.

## API Surface (1 function — starting small)

- **Calendars:** `get_calendars`

Planned (filed as issues): `create_event`, `get_events`, `update_event`, `update_events`, `delete_events`, `get_availability`

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

**Event UIDs work fine:** Individual event property access works: `uid of event`, `summary of event`, `start date of event`, etc.

**Variable naming conflicts:** Never use variable names that match Calendar properties. If Calendar has a `summary` property, don't use `summary` as a variable name — use `eventSummary`.

**JSON helpers duplicated:** AppleScript has no imports/modules. Every AppleScript block that returns JSON must include its own helper functions. This is intentional.

**Date format:** AppleScript returns dates as `"Monday, April 3, 2023 at 10:35:00 AM"` (locale-dependent, includes day name). The connector handles ISO 8601 conversion.

**String escaping:** Always use `_escape_applescript_string()` for user-provided text. Unescaped quotes break AppleScript blocks silently.

**Performance:** `whose` clause with date filtering timed out on large calendars (5600+ events). Event filtering strategy needs careful design.

## Calendar Safety

Destructive operations require `CALENDAR_TEST_MODE=true` and `CALENDAR_TEST_NAME=MCP-Test-Calendar` environment variables. Each destructive operation verifies the target calendar name before proceeding.

## Testing Requirements

| Type | When Required | How |
|------|--------------|-----|
| Unit tests | Every code change | `make test-unit` |
| Integration tests | New/modified AppleScript operations | `make test-integration` (requires test calendar) |

**Hard rule:** If you wrote or modified an AppleScript string in the connector, integration tests must cover that operation before merge. Unit tests mock `run_applescript()` and cannot catch AppleScript syntax errors.

## Branch Convention

`{type}/issue-{num}-{description}` — e.g., `feature/issue-1-get-calendars`, `fix/issue-5-date-parsing`

CHANGELOG.md is only updated on release branches, never on feature branches.

## Key Files

- `src/apple_calendar_mcp/calendar_connector.py` — Core AppleScript client
- `src/apple_calendar_mcp/server_fastmcp.py` — FastMCP server wrapping the connector
- `docs/research/calendar-api-gap-analysis.md` — What's possible, what's not
