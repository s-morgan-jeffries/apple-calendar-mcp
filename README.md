# Apple Calendar MCP Server

[![CI](https://github.com/s-morgan-jeffries/apple-calendar-mcp/actions/workflows/test.yml/badge.svg)](https://github.com/s-morgan-jeffries/apple-calendar-mcp/actions/workflows/test.yml)
[![Coverage](https://img.shields.io/badge/coverage-95%25-brightgreen)](https://github.com/s-morgan-jeffries/apple-calendar-mcp)
[![Python](https://img.shields.io/badge/python-3.10%2B-blue)](https://www.python.org)
[![License: MIT](https://img.shields.io/badge/license-MIT-green)](LICENSE)

A comprehensive, fast, reliable, and agent-friendly [MCP](https://modelcontextprotocol.io/) server for Apple Calendar on macOS.

## Why This Server

### Comprehensive

10 tools covering the full calendar lifecycle — more than any other dedicated Apple Calendar MCP server. Full CRUD for events and calendars, plus batch operations (`create_events`, `update_events`), text search, smart availability with working hours and minimum duration filters, and conflict detection. Complete recurring event support with iCalendar RRULE — create, update, and delete individual occurrences or entire series.

### Fast

All event operations use Swift/EventKit via native subprocess for sub-second performance, even on calendars with thousands of events. Calendar management uses AppleScript where it's fast enough.

| Operation | Typical Time | Notes |
|-----------|-------------|-------|
| List calendars | 0.5s | 16 calendars |
| Read events (1 month) | 0.6s | ~100 events |
| Read events (1 year) | 0.7s | ~1,400 events |
| Create event | 0.5s | |
| Update event | 0.6s | |
| Delete events (batch of 5) | 0.4s | Single commit |

### Reliable

95% code coverage from 215 unit tests. 57 integration tests run against real Calendar.app — covering round-trip data integrity, recurring event edge cases, special characters, alerts, year-boundary queries, and more. Calendar safety guards prevent accidental writes to real calendars during testing.

### Agent-Friendly

Every tool docstring includes detailed `Returns` sections documenting fields, types, and chaining info — so Claude knows that `create_events` returns UIDs usable by `update_events` without guessing. 38 blind agent eval scenarios validate tool usability across multiple models.

| Model | Score | Safety |
|-------|-------|--------|
| Mistral Large 2411 | 70/76 (92%) | 5/5 |
| DeepSeek V3 | 68/76 (89%) | 5/5 |
| Qwen 2.5 72B | 67/76 (88%) | 5/5 |
| Claude Sonnet 4 | 66/76 (87%) | 5/5 |
| Llama 3.3 70B | 59/76 (78%) | 5/5 |

All models pass all safety-critical scenarios. [Full results](evals/agent_tool_usability/results/scored_results.md).

## Tools (10)

### Calendars

| Tool | Description |
|------|-------------|
| `get_calendars` | List all calendars with names, access levels, descriptions, and colors |
| `create_calendar` | Create a new calendar |
| `delete_calendar` | Delete a calendar and all its events |

### Events

| Tool | Description |
|------|-------------|
| `get_events` | Query events in a date range |
| `search_events` | Search events by text across one or all calendars |
| `create_events` | Create one or more events in one operation |
| `update_events` | Update one or more events by UID, with full recurrence support |
| `delete_events` | Delete one or more events by UID |

### Scheduling

| Tool | Description |
|------|-------------|
| `get_availability` | Find free time slots across calendars, with optional working hours and minimum duration filters |
| `get_conflicts` | Detect double-bookings and overlapping events across calendars |

## Prerequisites

- **macOS** (Apple Calendar is macOS-only)
- **Python 3.10+**
- **Xcode Command Line Tools** — required for Swift helper compilation (`xcode-select --install`)

## Installation

```bash
# With uv (recommended)
uv tool install apple-calendar-mcp

# With pip
pip install apple-calendar-mcp
```

## Configuration

### Claude Desktop

Add to your Claude Desktop MCP config (`~/Library/Application Support/Claude/claude_desktop_config.json`):

```json
{
  "mcpServers": {
    "apple-calendar": {
      "command": "uvx",
      "args": ["apple-calendar-mcp"]
    }
  }
}
```

Or if running from a local clone:

```json
{
  "mcpServers": {
    "apple-calendar": {
      "command": "uv",
      "args": ["run", "--directory", "/path/to/apple-calendar-mcp", "python", "-m", "apple_calendar_mcp.server_fastmcp"]
    }
  }
}
```

### Other MCP Clients

Run the server directly:

```bash
apple-calendar-mcp
```

Or from source:

```bash
uv run python -m apple_calendar_mcp.server_fastmcp
```

## Permissions

On first use, macOS will prompt for calendar access permission. Grant access to allow the server to read and write calendar events. The Swift helpers use EventKit, which requires the "Full Disk Access" or "Calendars" permission depending on your macOS version.

## Development

```bash
make install           # Create venv and install dependencies
make test              # Run all tests (215 unit, 57 integration)
make test-unit         # Unit tests only
make test-integration  # Integration tests (requires test calendar)
make complexity        # Check cyclomatic complexity
make audit             # Check dependencies for vulnerabilities
```

All dates use ISO 8601 format in local time: `"2026-03-15"` for date-only or `"2026-03-15T14:30:00"` for date-time. Do not append "Z" — dates are not UTC.

## Contributing

See [CONTRIBUTING.md](CONTRIBUTING.md).

## License

[MIT](LICENSE)
