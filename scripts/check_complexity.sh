#!/bin/bash
# Check cyclomatic complexity of Python source files
# Fails if any function exceeds complexity threshold

THRESHOLD=10

echo "Checking cyclomatic complexity (threshold: $THRESHOLD)..."

if ! command -v radon &> /dev/null; then
    echo "radon not found. Install with: pip install radon"
    exit 1
fi

# Check complexity
RESULT=$(radon cc src/ -n "$THRESHOLD" -s 2>&1)

if [ -z "$RESULT" ]; then
    echo "All functions are within complexity threshold."
    exit 0
else
    echo "Functions exceeding complexity threshold:"
    echo "$RESULT"
    exit 1
fi
