# Security Policy

## Threat Model

This MCP server bridges an AI agent to Apple Calendar via EventKit. It can:

- **Read** calendars, events, availability, and conflicts
- **Write** events (create, update) and calendars (create)
- **Delete** events and calendars permanently

It cannot access the network, file system (beyond its own Swift helpers), or modify attendees. All operations go through Apple's EventKit framework, which enforces macOS calendar permissions.

**Trust boundary:** The MCP client (e.g., Claude Desktop) is the trust boundary. The server executes whatever the client requests — it has no authentication or authorization layer of its own. Security depends on the client's tool approval mechanism.

## Operational Security

### Destructive Operations

`delete_events` and `delete_calendar` are **permanent and irreversible**. There is no undo, recycle bin, or soft-delete. Deleted calendars and all their events are gone immediately.

`create_events` and `update_events` can also cause data loss (overwriting event fields, creating duplicates).

### Safety Guards Are Test-Only

The server includes calendar safety guards (`CALENDAR_TEST_MODE` + allowlisted calendar names) that restrict write operations to designated test calendars. **These guards are disabled in production.** They exist solely to protect real calendars during integration testing.

In production (Claude Desktop, etc.), all calendars are writable with no server-side restrictions.

### MCP Client Approval Is the Primary Safeguard

The MCP protocol requires clients to prompt users before executing tool calls. This approval dialog is the only thing standing between the agent and a destructive operation.

**Risk with auto-approve mode:** Some MCP clients support auto-approving tool calls. If auto-approve is enabled for this server, destructive operations execute without any human confirmation. Recommendations:

- Do not auto-approve this server's tools, or
- Scope auto-approve to read-only tools only (`get_calendars`, `get_events`, `search_events`, `get_availability`, `get_conflicts`)

## Supported Versions

Only the latest release receives security updates.

## Reporting a Vulnerability

Please report security vulnerabilities using [GitHub's private security advisory feature](https://github.com/s-morgan-jeffries/apple-calendar-mcp/security/advisories/new).

**Do not** open a public issue for security vulnerabilities.

### Timeline

- **Acknowledgment:** Within 48 hours
- **Assessment and response:** Within 7 days
