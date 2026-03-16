#!/bin/bash
# Create the test calendar in Calendar.app.
# Usage: ./scripts/test_setup.sh [calendar-name]
# Defaults to MCP-Test-Calendar.

set -euo pipefail

CALENDAR_NAME="${1:-MCP-Test-Calendar}"
SCRIPT_DIR="$(cd "$(dirname "$0")/.." && pwd)"

"${SCRIPT_DIR}/venv/bin/python" -c "
from tests.helpers.calendar_setup import create_test_calendar
created = create_test_calendar('${CALENDAR_NAME}')
if created:
    print('Created calendar: ${CALENDAR_NAME}')
else:
    print('Calendar already exists: ${CALENDAR_NAME}')
"
