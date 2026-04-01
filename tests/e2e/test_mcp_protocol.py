"""Tier 2 MCP protocol smoke tests — full stack through FastMCP transport.

Tests the complete path: MCP client → HTTP transport → FastMCP → tool function → Swift → EventKit.
Requires CALENDAR_TEST_MODE=true and a test calendar in Calendar.app.

All MCP tests run within a single server session to avoid event loop conflicts
with the module-level FastMCP singleton.
"""

import json
import os
from datetime import datetime

import pytest

pytestmark = [pytest.mark.e2e, pytest.mark.asyncio]

# Expected tool count — update if tools are added/removed
EXPECTED_TOOL_COUNT = 10


async def test_mcp_protocol_smoke_tests():
    """Run all MCP protocol smoke tests within a single server session."""
    if os.environ.get("CALENDAR_TEST_MODE") != "true":
        pytest.skip("MCP smoke tests require CALENDAR_TEST_MODE=true")

    from fastmcp.client import Client
    from fastmcp.client.transports import StreamableHttpTransport
    from fastmcp.utilities.tests import run_server_async

    from apple_calendar_mcp.server_fastmcp import mcp

    async with run_server_async(mcp) as url:
        async with Client(StreamableHttpTransport(url)) as client:

            # --- Tool Discovery ---

            # All 10 tools should be discoverable
            tools = await client.list_tools()
            tool_names = {t.name for t in tools}
            assert len(tools) == EXPECTED_TOOL_COUNT, f"Expected {EXPECTED_TOOL_COUNT} tools, got {len(tools)}: {tool_names}"
            expected = {
                "get_calendars", "create_calendar", "delete_calendar",
                "create_events", "update_events", "delete_events",
                "get_events", "search_events",
                "get_availability", "get_conflicts",
            }
            assert tool_names == expected

            # Every tool should have a description
            for tool in tools:
                assert tool.description, f"Tool {tool.name} has no description"

            # --- Calendar Operations ---

            # get_calendars should return formatted output with IDs
            cal_result = await client.call_tool("get_calendars", {})
            cal_text = cal_result.content[0].text
            assert "Found" in cal_text
            assert "calendar(s)" in cal_text
            assert "ID:" in cal_text

            # Parse out test calendar ID
            test_cal_name = os.environ.get("CALENDAR_TEST_NAME", "MCP-Test-Calendar")
            cal_id = None
            lines = cal_text.split("\n")
            for i, line in enumerate(lines):
                if "ID:" in line:
                    current_id = line.split("ID: ")[1].strip()
                if f"Name: {test_cal_name}" in line:
                    cal_id = current_id
                    break

            assert cal_id is not None, f"Test calendar '{test_cal_name}' not found in get_calendars output"

            # Create event through MCP
            year = datetime.now().year + 7
            event = [{
                "summary": "MCP Protocol Test Event",
                "start_date": f"{year}-01-20T10:00:00",
                "end_date": f"{year}-01-20T11:00:00",
            }]
            create_result = await client.call_tool(
                "create_events",
                {"calendar_id": cal_id, "events": json.dumps(event)},
            )
            create_text = create_result.content[0].text
            assert "Created 1 event(s)" in create_text

            # Read back through MCP
            get_result = await client.call_tool(
                "get_events",
                {"calendar_ids": [cal_id], "start_date": f"{year}-01-20", "end_date": f"{year}-01-20"},
            )
            get_text = get_result.content[0].text
            assert "MCP Protocol Test Event" in get_text

            # Cleanup
            uid = None
            for line in create_text.split("\n"):
                if "UID:" in line:
                    uid = line.split("UID: ")[1].strip().rstrip(")")
                    break
            if uid:
                await client.call_tool(
                    "delete_events",
                    {"calendar_id": cal_id, "event_uids": uid},
                )

            # --- Error Handling ---

            # Invalid JSON should return error, not crash
            error_result = await client.call_tool(
                "create_events",
                {"events": "not valid json"},
            )
            error_text = error_result.content[0].text
            assert "Error" in error_text
