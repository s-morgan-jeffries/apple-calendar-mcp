#!/bin/bash
# Install git hooks for branch protection, test enforcement, and release hygiene

echo "Installing git hooks..."
echo ""

# Install pre-commit hook
if [ -f ".git/hooks/pre-commit" ] || [ -L ".git/hooks/pre-commit" ]; then
    echo "  .git/hooks/pre-commit already exists, backing up"
    mv .git/hooks/pre-commit .git/hooks/pre-commit.backup
fi

ln -sf ../../scripts/git-hooks/pre-commit .git/hooks/pre-commit
echo "  Installed pre-commit hook"
echo "    - Blocks commits to main/master (except hotfixes)"
echo "    - Warns on version bump without CHANGELOG staged"
echo ""

# Install pre-push hook
if [ -f ".git/hooks/pre-push" ] || [ -L ".git/hooks/pre-push" ]; then
    echo "  .git/hooks/pre-push already exists, backing up"
    mv .git/hooks/pre-push .git/hooks/pre-push.backup
fi

ln -sf ../../scripts/git-hooks/pre-push .git/hooks/pre-push
echo "  Installed pre-push hook"
echo "    - Runs unit tests before push"
echo "    - Prevents pushing failing tests to remote"
echo ""

# Install pre-tag hook
if [ -f ".git/hooks/pre-tag" ] || [ -L ".git/hooks/pre-tag" ]; then
    echo "  .git/hooks/pre-tag already exists, backing up"
    mv .git/hooks/pre-tag .git/hooks/pre-tag.backup
fi

ln -sf ../../scripts/git-hooks/pre-tag .git/hooks/pre-tag
echo "  Installed pre-tag hook"
echo "    - Validates tag format (vX.Y.Z or vX.Y.Z-rcN)"
echo "    - Enforces branch requirements (RC on release/*, final on main)"
echo "    - Checks CHANGELOG date is not TBD"
echo ""

echo "Git hooks installed successfully!"
echo ""
echo "To uninstall:"
echo "  rm .git/hooks/pre-commit .git/hooks/pre-push .git/hooks/pre-tag"
