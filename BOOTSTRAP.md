# Apple Calendar MCP Server — Bootstrap Prompt

Use this prompt to bootstrap a new MCP server for Apple Calendar on macOS.

---

## Phase 0: API Research

Before writing any code, thoroughly investigate what's possible.

### AppleScript/SDEF Exploration
1. Dump the Calendar SDEF: `sdef /Applications/Calendar.app`
2. Document every class, property, command, and enumeration
3. For each capability, note whether it's read-only, read-write, or command-based
4. Test each capability against a real Calendar instance to verify behavior matches documentation
5. Pay special attention to:
   - What properties are readable but not writable
   - What operations require special handling (e.g., recurring events)
   - Date/time handling and timezone behavior
   - What's missing from the SDEF that exists in the UI

### EventKit / OmniAutomation-equivalent Investigation
- Check if Calendar has a JavaScript automation bridge (`evaluate javascript` or similar)
- Investigate whether JXA (JavaScript for Automation) provides capabilities beyond AppleScript
- Note any capabilities available through JXA but not AppleScript

### Gap Analysis Document
Create `docs/calendar-api-gap-analysis.md` documenting:
- Every Calendar feature visible in the UI
- Whether each feature is accessible via AppleScript, JXA, or neither
- Priority tiers (P1 = core CRUD, P2 = important workflows, P3 = niche)
- Open questions that need empirical testing

### Deliverable
A research document with concrete code examples for everything that works, filed as a GitHub issue and referenced in the gap analysis. This document drives the entire roadmap.

---

## Phase 1: Project Setup

### Repository Structure
```
apple-calendar-mcp/
├── src/apple_calendar_mcp/
│   ├── __init__.py
│   ├── calendar_connector.py    # AppleScript client (all Apple Event calls)
│   └── server_fastmcp.py        # FastMCP server wrapping the connector
├── tests/
│   ├── unit/                    # Mocked AppleScript — fast, run on every change
│   ├── integration/             # Real Calendar — requires test calendar
│   └── benchmarks/              # Performance profiling
├── evals/
│   └── agent_tool_usability/    # Blind agent evals for tool descriptions
├── docs/
│   ├── reference/               # Architecture, gotchas, automation notes
│   └── research/                # Research spikes
├── scripts/
│   ├── check_complexity.sh
│   ├── check_client_server_parity.sh
│   └── check_version_sync.sh
├── CLAUDE.md
├── Makefile
└── pyproject.toml
```

### Technology
- Python 3.10+, FastMCP, AppleScript (via `osascript`)
- `uv` for dependency management
- GitHub Issues + Milestones for tracking

### GitHub Setup
- Create milestones: v0.1.0 (core CRUD), v0.2.0 (filters/queries), v0.3.0 (recurring events), etc.
- Branch convention: `{type}/issue-{num}-{description}` (e.g., `feature/issue-12-create-event`)
- Squash merge PRs; never commit directly to main
- File issues from the gap analysis, one per capability or group of related capabilities

---

## Phase 2: API Design Philosophy

### Core Principles

1. **Fewer, more powerful functions.** Resist adding specialized functions. A `get_events` with good filtering is better than `get_today_events`, `get_upcoming_events`, `get_events_by_calendar`, etc. Start with the minimum viable set and only add functions when there's a clear, demonstrated need.

2. **Comprehensive update functions over field-specific setters.** One `update_event(event_id, title=X, start_date=Y, notes=Z)` — not `set_event_title()`, `set_event_date()`, etc.

3. **Structured returns always.** Every function returns `dict` or `list[dict]`, never formatted text strings. The agent decides how to present data to the user.

4. **Separate single/batch operations.** `update_event` (single, all fields) vs `update_events` (batch, limited fields). Batch excludes fields that require unique values (like title).

5. **No upsert pattern.** Create and update are always separate operations.

6. **Union types for deletes only.** `delete_events(event_id: Union[str, list[str]])` — not for updates.

### Decision Tree for New Functions
Before adding any new function, ask:
1. Can an existing function handle this with an additional parameter?
2. Is this a field-specific getter/setter? (If yes, don't add it.)
3. Will agents actually need this, or is it speculative?
4. Does this increase the API surface without proportional value?

### Likely Initial API Surface
Based on typical calendar operations (refine after SDEF research):

- **Events:** `create_event`, `get_events`, `update_event`, `update_events`, `delete_events`
- **Calendars:** `get_calendars`, `create_calendar` (maybe)
- **Availability:** `get_availability` (free/busy lookup)

Keep it small. You can always add; you can't easily remove.

---

## Phase 3: Implementation

### Architecture: Two-Layer Design

**Connector layer** (`calendar_connector.py`):
- All AppleScript generation and execution
- Returns Python dicts/lists
- Handles date conversion, string escaping, error mapping
- No MCP awareness — pure Calendar client

**Server layer** (`server_fastmcp.py`):
- FastMCP `@mcp.tool()` decorators
- Parameter validation, JSON parsing
- Docstrings ARE the agent-facing tool descriptions (they're exposed via MCP protocol)
- Server `instructions=` block is the MCP system prompt — treat it as agent-facing documentation
- Thin wrapper over connector methods

### AppleScript Patterns and Gotchas

These lessons are hard-won from the OmniFocus MCP project. Calendar will have its own quirks, but these patterns transfer:

1. **Variable naming conflicts.** Never use variable names that match Calendar properties. If Calendar has a `title` property, don't use `title` as a variable name — use `eventTitle`. This causes silent bugs where AppleScript reads the property instead of the variable.

2. **String escaping.** Always escape user-provided text before embedding in AppleScript. Unescaped quotes break scripts silently. Write an `_escape_applescript_string()` helper and use it everywhere.

3. **Date handling.** AppleScript uses locale-dependent date formats like `"March 5, 2026 5:00:00 PM"`. Write `_iso_to_applescript_date()` and `_applescript_date_to_iso()` helpers for ISO 8601 conversion. Test timezone behavior carefully.

4. **JSON helpers must be duplicated.** AppleScript has no imports/modules. Every AppleScript block that returns JSON needs its own helper functions inline. This is intentional duplication.

5. **Recurring events need special handling.** Investigate how Calendar handles recurring event modifications — does modifying one instance affect the series? Document this thoroughly.

6. **Performance: IPC is the bottleneck.** Each property read from a macOS app via AppleScript costs ~10-20ms (inter-process communication). Reading 20 properties from 500 events = slow. Use `whose` clauses to pre-filter, then extract properties only from the result set.

### Test-Driven Development (Mandatory)

**Always write the failing test BEFORE writing production code. No exceptions.**

1. Write one test
2. Run it — watch it fail
3. Write the minimal code to make it pass
4. Refactor if needed
5. Repeat

Never write production code first and tests after.

### Testing Tiers

| Tier | When Required | What It Catches |
|------|--------------|-----------------|
| **Unit tests** | Every code change | Logic errors, parameter handling, response formatting |
| **Integration tests** | New/modified AppleScript | Syntax errors, variable conflicts, property access failures, behavioral quirks |
| **Performance benchmarks** | Filter/fetch path changes | IPC bottlenecks, timeout issues |
| **Blind agent evals** | Tool description or interface changes | Whether an AI agent can figure out how to use the tools correctly from the descriptions alone |

**Hard rule:** If you wrote or modified an AppleScript string in the connector, integration tests must cover that operation before merge. Unit tests mock `run_applescript()` and CANNOT catch AppleScript syntax errors, variable naming collisions, or behavioral quirks.

### Test Calendar Isolation
- Create a dedicated test calendar (e.g., "MCP-Test-Calendar") for integration tests
- Destructive operations should verify they're operating on the test calendar before proceeding
- Use environment variables (e.g., `CALENDAR_TEST_MODE=true`, `CALENDAR_TEST_NAME=MCP-Test-Calendar`) as safety guards
- Write switch scripts for test/production if needed

### Blind Agent Evals
When tool descriptions or MCP signatures change:
1. Create scenarios that test whether an agent can figure out how to accomplish tasks using only the tool descriptions
2. Run scenarios against the current tool descriptions
3. Score results before merging

The tool descriptions are the UX. If an agent can't figure out how to use a tool from its description, the description is wrong — not the agent.

---

## Phase 4: Documentation

### Agent-Facing Documentation (Critical)
Two things are exposed to agents via MCP:
1. **`instructions=` block** on the FastMCP server — this is the system prompt
2. **Function docstrings** on `@mcp.tool()` functions — these become tool descriptions

Changes to either of these are interface changes. They require blind evals before merging.

### Internal Documentation
- `docs/reference/ARCHITECTURE.md` — API design rationale, why functions exist
- `docs/reference/APPLESCRIPT_GOTCHAS.md` — Calendar-specific AppleScript limitations
- `docs/calendar-api-gap-analysis.md` — What's possible, what's not, priorities
- `CLAUDE.md` — Developer instructions, commands, key files

### CLAUDE.md Should Include
- How to run each test tier
- API surface summary
- Core design principles (so future sessions don't re-add functions you deliberately excluded)
- AppleScript gotchas specific to Calendar
- Performance constraints and baselines
- Branch convention and PR workflow
- Key file paths

---

## Phase 5: Ongoing Practices

### Before Each Release
1. Run all test tiers
2. Run blind evals if tool descriptions changed
3. Update CHANGELOG.md (only on release branches)
4. Version bump, tag on main after merge

### Resist Scope Creep
- The API was designed to be small. Keep it small.
- File feature requests as issues; don't implement speculatively
- Every new function needs to pass the decision tree
- "Can the agent accomplish this with existing tools?" — if yes, don't add a new one

### Performance Baselines
After initial implementation, profile every operation and document baselines:
- Single event CRUD: target < 1s
- Filtered queries: document actual timings
- Identify the IPC bottleneck early and design around it

---

## Quick Start Checklist

1. [ ] Create GitHub repo
2. [ ] Set up project structure and `pyproject.toml`
3. [ ] Dump Calendar SDEF and create gap analysis
4. [ ] File issues from gap analysis, assign to milestones
5. [ ] Write CLAUDE.md with initial instructions
6. [ ] Implement `run_applescript()` helper with escaping and date conversion
7. [ ] TDD: first test + first tool (`get_calendars` is a good starting point)
8. [ ] Set up integration test calendar and safety guards
9. [ ] Build out core CRUD following the API design principles
10. [ ] Write blind eval scenarios once tool descriptions stabilize
