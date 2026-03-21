#!/bin/bash
# Check if CHANGELOG.md date has been updated from "TBD" before final release tag

TAG_NAME="${1:-}"

echo "Checking CHANGELOG.md date..."

VERSION=$(grep '^version = ' pyproject.toml | cut -d'"' -f2)

if [ -z "$VERSION" ]; then
    echo "Could not read version from pyproject.toml"
    exit 1
fi

echo "   Current version: $VERSION"

if [ ! -f "CHANGELOG.md" ]; then
    echo "CHANGELOG.md not found"
    exit 1
fi

CHANGELOG_LINE=$(grep -E "^## \[$VERSION\]" CHANGELOG.md | head -1)

if [ -z "$CHANGELOG_LINE" ]; then
    echo "Version $VERSION not found in CHANGELOG.md"
    echo "   Expected format: ## [$VERSION] - DATE"
    exit 1
fi

CHANGELOG_DATE=$(echo "$CHANGELOG_LINE" | sed -E 's/^## \[[^]]+\] - (.+)$/\1/')

echo "   CHANGELOG date: $CHANGELOG_DATE"
echo ""

if [ "$CHANGELOG_DATE" = "TBD" ]; then
    echo "CHANGELOG.md still has 'TBD' date!"
    echo "   Version: $VERSION"
    echo "   Current line: $CHANGELOG_LINE"
    echo ""
    echo "Action required:"
    echo "   1. Update CHANGELOG.md to replace 'TBD' with actual release date"
    echo "   2. Format: ## [$VERSION] - YYYY-MM-DD"
    echo "   3. Commit the date update"
    echo "   4. Then create the release tag"
    exit 1
fi

if echo "$CHANGELOG_DATE" | grep -qE '^[0-9]{4}-[0-9]{2}-[0-9]{2}$'; then
    DATE_FORMAT="Valid format (YYYY-MM-DD)"
else
    DATE_FORMAT="Non-standard format (expected YYYY-MM-DD)"
fi

echo "CHANGELOG.md date is set!"
echo "   Version: $VERSION"
echo "   Date: $CHANGELOG_DATE"
echo "   $DATE_FORMAT"
exit 0
