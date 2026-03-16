#!/bin/bash
# Delete the test calendar from Calendar.app.
# Usage: ./scripts/test_teardown.sh [calendar-name]
# Defaults to MCP-Test-Calendar.

set -euo pipefail

CALENDAR_NAME="${1:-MCP-Test-Calendar}"
SCRIPT_DIR="$(cd "$(dirname "$0")/.." && pwd)"

"${SCRIPT_DIR}/venv/bin/python" -c "
from tests.helpers.calendar_setup import delete_test_calendar
deleted = delete_test_calendar('${CALENDAR_NAME}')
if deleted:
    print('Deleted calendar: ${CALENDAR_NAME}')
else:
    print('Calendar not found: ${CALENDAR_NAME}')
"
