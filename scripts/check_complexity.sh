#!/bin/bash
# Check cyclomatic complexity of Python source files
# Fails if any function has complexity grade C or worse (CC > 10)
#
# Radon grades: A (1-5), B (6-10), C (11-15), D (16-20), E (21-25), F (26+)
#
# Documented exceptions (tracked in issue #158):
#   get_availability: CC=20 — multi-step availability calculation
#   get_conflicts: CC=11 — pairwise overlap detection with filtering

echo "Checking cyclomatic complexity (max allowed: B, CC ≤ 10)..."

if ! command -v radon &> /dev/null; then
    echo "radon not found. Install with: pip install radon"
    exit 1
fi

# Show only functions with grade C or worse (complexity > 10)
RESULT=$(radon cc src/ -n C -s 2>&1)

if [ -z "$RESULT" ]; then
    echo "All functions are within complexity threshold."
    exit 0
fi

# Filter out documented exceptions
EXCEPTIONS="get_availability|get_conflicts"
FILTERED=$(echo "$RESULT" | grep -v -E "$EXCEPTIONS")

# Check if any non-excepted functions remain
if [ -z "$FILTERED" ] || [ "$(echo "$FILTERED" | grep -c '^\s*[A-Z]')" -eq 0 ]; then
    echo "All functions within threshold (with documented exceptions)."
    echo ""
    echo "Documented exceptions (issue #158):"
    echo "$RESULT" | grep -E "$EXCEPTIONS" | sed 's/^/  /'
    exit 0
else
    echo "Functions exceeding complexity threshold:"
    echo "$FILTERED"
    exit 1
fi
