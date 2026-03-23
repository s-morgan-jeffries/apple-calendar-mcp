#!/bin/bash
# Run performance benchmarks against real Calendar.app.
# Usage: ./scripts/benchmark_performance.sh [read-calendar-name] [--output FILE]
#
# Write operations use MCP-Test-Calendar (created automatically).
# Read operations use the specified calendar (default: MCP-Test-Calendar).
# Pass a calendar with many events to test large-calendar performance.
# Use --output FILE to save JSON results for historical comparison.

set -euo pipefail

SCRIPT_DIR="$(cd "$(dirname "$0")/.." && pwd)"
READ_CALENDAR="${1:-MCP-Test-Calendar}"
shift || true

# Ensure test calendar exists
"${SCRIPT_DIR}/scripts/test_setup.sh" >/dev/null

echo "Read calendar: ${READ_CALENDAR}"
echo ""

CALENDAR_TEST_MODE=true CALENDAR_TEST_NAME="MCP-Test-Calendar" \
    "${SCRIPT_DIR}/venv/bin/python" -m tests.benchmarks.performance \
    --read-calendar "${READ_CALENDAR}" \
    --test-calendar "MCP-Test-Calendar" \
    "$@"
