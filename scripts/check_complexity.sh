#!/bin/bash
# Check cyclomatic complexity of Python source files
# Fails if any function has complexity grade D or worse (CC > 15)
#
# Radon grades: A (1-5), B (6-10), C (11-15), D (16-20), E (21-25), F (26+)
# Note: Threshold temporarily raised from C to D for v0.5.0. See #77 for refactoring plan.

echo "Checking cyclomatic complexity (max allowed: C, CC ≤ 15)..."

if ! command -v radon &> /dev/null; then
    echo "radon not found. Install with: pip install radon"
    exit 1
fi

# Show only functions with grade D or worse (complexity > 15)
RESULT=$(radon cc src/ -n D -s 2>&1)

if [ -z "$RESULT" ]; then
    echo "All functions are within complexity threshold."
    exit 0
else
    echo "Functions exceeding complexity threshold:"
    echo "$RESULT"
    exit 1
fi
