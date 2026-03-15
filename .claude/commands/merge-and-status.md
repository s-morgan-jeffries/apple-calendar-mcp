Merge the current PR, pull main, and show open milestone issues.

## Steps

1. **Find the open PR** for the current branch:
   ```bash
   gh pr list --head "$(git branch --show-current)" --state open --json number --jq '.[0].number'
   ```

2. **Squash merge** the PR and delete the branch:
   ```bash
   gh pr merge <number> --squash --delete-branch
   ```

3. **Switch to main and pull:**
   ```bash
   git checkout main && git pull
   ```

4. **Determine the current milestone.** Find the earliest open milestone:
   ```bash
   gh api repos/:owner/:repo/milestones --jq 'sort_by(.due_on // .title) | map(select(.state == "open")) | .[0].title'
   ```

5. **List open issues** on that milestone:
   ```bash
   gh issue list --milestone "<milestone>" --state open
   ```

6. **Display results** as a formatted table with issue number, title, and labels.
