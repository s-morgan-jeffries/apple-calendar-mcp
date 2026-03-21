#!/bin/bash
# Check that all public connector functions have corresponding MCP tools

CLIENT_FILE="src/apple_calendar_mcp/calendar_connector.py"
SERVER_FILE="src/apple_calendar_mcp/server_fastmcp.py"

echo "Checking client/server parity..."
echo ""

# Extract public function names from connector (exclude private/internal)
CLIENT_FUNCTIONS=$(grep -E "^    def [a-z][a-z_]*\(" "$CLIENT_FILE" | \
    grep -v "def _" | \
    sed 's/.*def \([a-z_]*\).*/\1/' | \
    sort | uniq)

# Extract tool function names from server
SERVER_TOOLS=$(grep -A1 "@mcp.tool()" "$SERVER_FILE" | \
    grep "^def " | \
    sed 's/def \([a-z_]*\).*/\1/' | \
    sort | uniq)

# Find functions missing from server
MISSING=()
for func in $CLIENT_FUNCTIONS; do
    if ! echo "$SERVER_TOOLS" | grep -q "^${func}$"; then
        MISSING+=("$func")
    fi
done

# Display results
if [ ${#MISSING[@]} -eq 0 ]; then
    echo "Client/server parity check PASSED"
    echo ""
    echo "All $(echo "$CLIENT_FUNCTIONS" | wc -l | tr -d ' ') connector functions have corresponding MCP tools."
    exit 0
else
    echo "Client/server parity check FAILED"
    echo ""
    echo "The following connector functions are missing MCP tool exposure:"
    printf '  - %s\n' "${MISSING[@]}"
    echo ""
    echo "Action required:"
    echo "1. Add @mcp.tool() wrapper in $SERVER_FILE for each missing function"
    echo "2. Re-run this check"
    exit 1
fi
