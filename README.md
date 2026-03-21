# Apple Calendar MCP Server

[![CI](https://github.com/s-morgan-jeffries/apple-calendar-mcp/actions/workflows/test.yml/badge.svg)](https://github.com/s-morgan-jeffries/apple-calendar-mcp/actions/workflows/test.yml)
[![Python](https://img.shields.io/badge/python-3.10%2B-blue)](https://www.python.org)
[![License: MIT](https://img.shields.io/badge/license-MIT-green)](LICENSE)

An [MCP](https://modelcontextprotocol.io/) server that connects Claude to Apple Calendar on macOS via AppleScript and EventKit.

## Features

- **get_calendars** — List all calendars with names, access levels, and colors
- **get_events** — Query events in a date range (fast, uses EventKit)
- **create_event** — Create events with title, dates, location, notes, URL
- **update_event** — Update any event field by UID
- **delete_events** — Delete one or more events by UID (batch support)

## Requirements

- macOS
- Python 3.10+
- Calendar.app (ships with macOS)

## Installation

```bash
# With uv (recommended)
uv tool install apple-calendar-mcp

# With pip
pip install apple-calendar-mcp
```

On first use, macOS will prompt for calendar access permission.

## Usage with Claude Desktop

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

## Tools

| Tool | Parameters | Description |
|------|-----------|-------------|
| `get_calendars` | — | List all calendars with name, access level, description, color |
| `get_events` | `calendar_name`, `start_date`, `end_date` | Get events in a date range (ISO 8601 dates) |
| `create_event` | `calendar_name`, `summary`, `start_date`, `end_date`, `location?`, `description?`, `url?`, `allday_event?` | Create a new event |
| `update_event` | `calendar_name`, `event_uid`, `summary?`, `start_date?`, `end_date?`, `location?`, `description?`, `url?`, `allday_event?` | Update event fields (only provided fields change) |
| `delete_events` | `calendar_name`, `event_uid` (str or list) | Delete one or more events by UID |

All dates use ISO 8601 format: `"2026-03-15"` for date-only or `"2026-03-15T14:30:00"` for date-time.

Calendar names are not guaranteed unique — the same name can appear across different accounts (e.g., two "Family" calendars from iCloud and Google). Use `get_calendars` to check descriptions when disambiguating.

## Development

```bash
make install           # Create venv and install dependencies
make test              # Run all tests (147 unit, 57 integration)
make test-unit         # Unit tests only
make test-integration  # Integration tests (requires test calendar)
make test-verbose      # Tests with verbose output
```

Integration tests automatically create and tear down an `MCP-Test-Calendar` in Calendar.app. You can also manage it manually:

```bash
./scripts/test_setup.sh      # Create test calendar
./scripts/test_teardown.sh   # Delete test calendar
```

## Architecture

The server uses a hybrid approach for performance:

- **Writes** (create, update, delete) use AppleScript via `osascript` — fast for single-event operations
- **Reads** (get_events) use Swift/EventKit via a compiled helper — native date-range queries, sub-second on any calendar size

AppleScript event reads are too slow for large calendars (5600+ events caused timeouts), so `get_events` delegates to EventKit instead.

## License

MIT
