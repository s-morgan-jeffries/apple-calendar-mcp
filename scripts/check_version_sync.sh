#!/bin/bash
# Verify version is consistent across pyproject.toml, CLAUDE.md, and __init__.py

PYPROJECT_VERSION=$(grep 'version = ' pyproject.toml | head -1 | sed 's/.*"\(.*\)".*/\1/')
CLAUDE_VERSION=$(grep -oE 'v[0-9]+\.[0-9]+\.[0-9]+' .claude/CLAUDE.md | head -1 | sed 's/v//')
INIT_VERSION=$(grep '__version__' src/apple_calendar_mcp/__init__.py | sed 's/.*"\(.*\)".*/\1/')

echo "pyproject.toml: $PYPROJECT_VERSION"
echo "CLAUDE.md:      $CLAUDE_VERSION"
echo "__init__.py:    $INIT_VERSION"

MISMATCH=0
if [ "$PYPROJECT_VERSION" != "$CLAUDE_VERSION" ]; then
    echo "ERROR: pyproject.toml and CLAUDE.md versions differ!"
    MISMATCH=1
fi
if [ "$PYPROJECT_VERSION" != "$INIT_VERSION" ]; then
    echo "ERROR: pyproject.toml and __init__.py versions differ!"
    MISMATCH=1
fi

if [ "$MISMATCH" -eq 0 ]; then
    echo "Versions are in sync."
    exit 0
else
    exit 1
fi
