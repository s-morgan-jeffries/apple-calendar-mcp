#!/bin/bash
# Verify version is consistent across pyproject.toml and CLAUDE.md

PYPROJECT_VERSION=$(grep 'version = ' pyproject.toml | head -1 | sed 's/.*"\(.*\)".*/\1/')
CLAUDE_VERSION=$(grep -oE 'v[0-9]+\.[0-9]+\.[0-9]+' .claude/CLAUDE.md | head -1 | sed 's/v//')

echo "pyproject.toml: $PYPROJECT_VERSION"
echo "CLAUDE.md:      $CLAUDE_VERSION"

if [ "$PYPROJECT_VERSION" = "$CLAUDE_VERSION" ]; then
    echo "Versions are in sync."
    exit 0
else
    echo "ERROR: Version mismatch!"
    exit 1
fi
