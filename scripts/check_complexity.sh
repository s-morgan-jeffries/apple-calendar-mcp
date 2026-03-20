#!/bin/bash
# Check cyclomatic complexity of Python source files
# Fails if any function has complexity grade C or worse (CC > 10)
#
# Radon grades: A (1-5), B (6-10), C (11-15), D (16-20), E (21-25), F (26+)

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
else
    echo "Functions exceeding complexity threshold:"
    echo "$RESULT"
    exit 1
fi
