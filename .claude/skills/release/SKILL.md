---
name: release
description: Use when the user wants to release a new version, says "time to release", "let's release", "cut a release", "version bump", or similar. Orchestrates the full release workflow including milestone check, version bump, changelog generation, validation, tagging, and PR creation. Also invocable as /release.
---

# Release Workflow

This skill orchestrates a complete release. Follow each phase in order. Stop and report if any phase fails.

## Phase 1: Milestone Check

Before creating a release branch, verify the milestone is ready.

1. Determine the target milestone. Look at open milestones:
   ```bash
   gh api "repos/{owner}/{repo}/milestones?state=open&sort=due_on" --jq '.[] | "\(.number) \(.title) open:\(.open_issues) closed:\(.closed_issues)"'
   ```

2. If there are multiple open milestones, ask the user which one to release.

3. If the target milestone has open issues, **stop and ask the user**:
   - List the open issues: `gh issue list --milestone "<title>" --state open`
   - Present options:
     a. Move open issues to the next milestone (specify or create it)
     b. Pause to work on the open issues first
     c. Close the issues if they're no longer relevant
   - Do NOT proceed until all issues in the target milestone are closed or moved.

4. Once the milestone is clean (0 open issues), proceed.

## Phase 2: Version Number

1. Read the current version from `pyproject.toml` (authoritative source).
2. The milestone title tells you the target version (e.g., `v0.1.0` means version `0.1.0`).
3. Validate it's a valid semver bump from the current version.
4. Present the version to the user for confirmation: "Release version X.Y.Z? (current: A.B.C)"
5. Wait for confirmation before proceeding.

## Phase 3: Create Release Branch

```bash
git checkout main
git pull origin main
git checkout -b release/vX.Y.Z
```

## Phase 4: Bump Version

Update version in ALL of these files (pyproject.toml is authoritative):

1. **pyproject.toml** - `version = "X.Y.Z"`
2. **CLAUDE.md** (.claude/CLAUDE.md) - `**Version:** vX.Y.Z` in the header line

Use the Edit tool for each file. Be precise about what to change.

## Phase 5: Generate CHANGELOG

1. Get all commits since the last release:
   ```bash
   git log v{previous_version}..HEAD --oneline
   ```
   Use the previous version tag directly (e.g., `v0.1.0`). Do NOT use `git describe --tags --abbrev=0` — it walks commit ancestry and may not find tags that were created before a squash/rebase merge.

2. Get merged PRs since the last release:
   ```bash
   gh pr list --state merged --base main --search "merged:>YYYY-MM-DD" --json number,title,labels
   ```
   (Use the date of the last tag, or the first commit date for the initial release)

3. Generate a CHANGELOG entry following the existing format in CHANGELOG.md (create the file if it doesn't exist):
   - Use Keep a Changelog format: `## [X.Y.Z] - YYYY-MM-DD`
   - Categorize changes: Added, Changed, Fixed, Removed
   - Reference PR/issue numbers with (#N)
   - Be concise but descriptive
   - Include today's date

4. Insert the new entry at the top of CHANGELOG.md (after the header, before the previous version).

## Phase 6: Validation

Run ALL validation checks. Stop on any failure.

1. **Version sync check:**
   ```bash
   ./scripts/check_version_sync.sh
   ```

2. **Complexity check:**
   ```bash
   ./scripts/check_complexity.sh
   ```

3. **Unit tests:**
   ```bash
   make test
   ```

4. **Integration tests** (optional — requires real Calendar + test calendar):
   Ask the user if they want to run integration tests:
   ```bash
   make test-integration
   ```

If any check fails, fix the issue and re-run. Do not proceed with failures.

## Phase 7: Commit, Push, and PR

1. **Commit** the version bump and changelog:
   ```bash
   git add -A
   git commit -m "release: vX.Y.Z"
   ```

2. **Push** the branch:
   ```bash
   git push -u origin release/vX.Y.Z
   ```

3. **Create the PR** to main:
   ```bash
   gh pr create --title "release: vX.Y.Z" --body "..."
   ```

4. Tell the user the PR is ready for review. Do NOT merge it automatically.

## Phase 8: Merge, Tag, and Push Tag

After the user approves the PR:

1. **Merge** using rebase merge:
   ```bash
   gh pr merge NNN --rebase --delete-branch
   ```

2. **Switch to main and pull:**
   ```bash
   git checkout main
   git pull origin main
   ```

3. **Create the tag on main** (where it will be reachable via `git describe`):
   ```bash
   ./scripts/create_tag.sh vX.Y.Z
   ```

4. **Push the tag:**
   ```bash
   git push origin vX.Y.Z
   ```

5. **Verify** tag reachability:
   ```bash
   git describe --tags --abbrev=0  # Should return vX.Y.Z
   ```

## Phase 9: Close Milestone

After the tag is pushed, close the milestone:

```bash
gh api -X PATCH "repos/{owner}/{repo}/milestones/{number}" -f state=closed
```

## Notes

- CHANGELOG is only updated on release branches, never on feature branches.
- Tags are created on main **after** the PR merge. This ensures they are reachable via `git describe`, which walks commit ancestry. Squash/rebase merges create new commits, so tags on the release branch would become orphaned.
- Use **rebase merge** for release PRs. Merge commits are blocked by `required_linear_history` on main (if enabled).
- Integration tests (`make test-integration`) require a real Calendar.app test calendar. Ask the user if they want to run them — they're optional for the release validation.
