#!/bin/bash
# Check for known security vulnerabilities in dependencies.
# Uses pip-audit against the PyPI/OSV vulnerability database.
#
# Install: pip install pip-audit
# Usage: ./scripts/check_dependencies.sh

set -euo pipefail

echo "Checking dependencies for known vulnerabilities..."
echo ""

# Check pip-audit is available
if ! command -v pip-audit &> /dev/null; then
    if [ -f "./venv/bin/pip-audit" ]; then
        PIP_AUDIT="./venv/bin/pip-audit"
    else
        echo "ERROR: pip-audit not found."
        echo "Install it: pip install pip-audit"
        exit 1
    fi
else
    PIP_AUDIT="pip-audit"
fi

if $PIP_AUDIT 2>&1; then
    echo ""
    echo "Dependency audit PASSED — no known vulnerabilities found."
    exit 0
else
    echo ""
    echo "Dependency audit FAILED — vulnerabilities found above."
    echo "Run 'pip-audit --fix' to attempt automatic fixes, or update affected packages manually."
    exit 1
fi
