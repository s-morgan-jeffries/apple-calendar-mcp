#!/bin/bash
# Create a git tag with format validation
# Usage: ./scripts/create_tag.sh <tag-name>
# Example: ./scripts/create_tag.sh v0.1.0

set -e

RED='\033[0;31m'
GREEN='\033[0;32m'
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

# Check if tag already exists
if git tag -l | grep -q "^${TAG_NAME}$"; then
    echo -e "${RED}Error: Tag ${TAG_NAME} already exists${NC}"
    echo "To delete and recreate: git tag -d ${TAG_NAME}"
    exit 1
fi

# Create the tag
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
