#!/bin/bash
# Automated tag creation with pre-tag hygiene checks
# Usage: ./scripts/create_tag.sh <tag-name>
#
# This script automates the tag creation workflow by:
# 1. Running pre-tag hygiene checks (branch, format, changelog date)
# 2. Creating the git tag if checks pass

set -e

RED='\033[0;31m'
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
NC='\033[0m'

if [ -z "$1" ]; then
    echo -e "${RED}Error: Tag name required${NC}"
    echo "Usage: $0 <tag-name>"
    echo "Example: $0 v0.1.0"
    exit 1
fi

TAG_NAME="$1"

# Validate tag name format (vX.Y.Z or vX.Y.Z-rcN)
if ! echo "$TAG_NAME" | grep -qE '^v[0-9]+\.[0-9]+\.[0-9]+(-rc[0-9]+)?$'; then
    echo -e "${RED}Error: Invalid tag name format${NC}"
    echo "Tag name must follow pattern: vX.Y.Z or vX.Y.Z-rcN"
    echo "Examples: v0.1.0, v0.2.0-rc1"
    exit 1
fi

# Get project root (parent of scripts directory)
SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
PROJECT_ROOT="$(cd "$SCRIPT_DIR/.." && pwd)"

# Check if tag already exists
if git tag -l | grep -q "^${TAG_NAME}$"; then
    echo -e "${RED}Error: Tag ${TAG_NAME} already exists${NC}"
    echo "To delete and recreate: git tag -d ${TAG_NAME}"
    exit 1
fi

# Check if pre-tag hook exists and is executable
PRE_TAG_HOOK="$PROJECT_ROOT/scripts/git-hooks/pre-tag"
if [ ! -f "$PRE_TAG_HOOK" ]; then
    echo -e "${RED}Error: Pre-tag hook not found at $PRE_TAG_HOOK${NC}"
    exit 1
fi

if [ ! -x "$PRE_TAG_HOOK" ]; then
    echo -e "${RED}Error: Pre-tag hook is not executable${NC}"
    echo "Run: chmod +x $PRE_TAG_HOOK"
    exit 1
fi

# Display what we're about to do
echo -e "${YELLOW}========================================${NC}"
echo -e "${YELLOW}Automated Tag Creation${NC}"
echo -e "${YELLOW}========================================${NC}"
echo "Tag name: ${TAG_NAME}"
echo ""

# Run pre-tag hygiene checks
echo -e "${YELLOW}Step 1: Running pre-tag hygiene checks...${NC}"
echo ""

if "$PRE_TAG_HOOK" "$TAG_NAME"; then
    echo ""
    echo -e "${GREEN}Hygiene checks passed${NC}"
    echo ""
else
    EXIT_CODE=$?
    echo ""
    echo -e "${RED}Hygiene checks failed (exit code: $EXIT_CODE)${NC}"
    echo ""
    echo "Review the output above to see what failed."
    echo "Fix the issues and try again."
    echo ""
    exit $EXIT_CODE
fi

# Create the tag
echo -e "${YELLOW}Step 2: Creating git tag...${NC}"
if git tag "$TAG_NAME"; then
    echo -e "${GREEN}Tag ${TAG_NAME} created successfully${NC}"
    echo ""
    echo "Next steps:"
    echo "1. Review the tag: git show ${TAG_NAME}"
    echo "2. Push the tag: git push origin ${TAG_NAME}"
else
    echo -e "${RED}Failed to create tag${NC}"
    exit 1
fi
