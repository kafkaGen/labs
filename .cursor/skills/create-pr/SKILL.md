---
name: create-pr
description: >-
  Create or update a GitHub pull request with the GitHub CLI: read branch
  commits, write title and body, target main. Use when the user asks to create,
  open, update, or refresh a PR or MR.
disable-model-invocation: true
---

# Create PR

Use **`gh`**, never GitHub MCP. Never open a PR from `main`. If still on `main`, stop — `/git-commit` creates the topic branch on first commit.

**Safety:** never update git config, skip hooks, or force-push `main`.

Before creating a PR, check whether one already exists for this branch. If it does, **update that PR** (title and body) instead of opening a second one. Don't ask; the existing PR is the one to keep current.

## Workflow

1. **Inspect the branch.** Know the current branch and every commit on it since it diverged from `main`. The commit messages are the source of truth for the PR: they already say what changed and why. Read all of them. Use the diff only to clarify a message that is ambiguous, never as the primary input.

```bash
git status
git fetch origin
git branch --show-current
git log --format='%h %s%n%b' origin/main..HEAD
```

If a commit message isn't enough, clarify with:

```bash
git diff origin/main...HEAD
```

Fill the body template below from those commits. Do not look for a repo PR template. Do not dump file paths.

2. **Check for an existing PR** on this branch against `main`:

```bash
gh pr view --json number,url,title
```

No open PR for this branch: `gh` exits non-zero. Create in step 4. An open PR: update it in step 4. Never create a second PR for the same branch.

3. **Issue is optional.** Link one only when the user named it or a commit already has `Closes #N` / `Refs #N`. Do not search GitHub for a matching issue. Do not invent a link.

If this PR finishes that work: `Closes #N` in the PR body. Related but unfinished: `Refs #N`. If nothing was named, omit the Issue section.

To confirm a named issue exists:

```bash
gh issue view <N>
```

Do not close the issue with `gh issue close`. `Closes #N` in the body is enough.

4. **Push, then create or update.** `base` is always `main`. Title: `type(scope): summary` (same as `/git-commit`). Return the PR URL when done.

Push if the branch is not on origin yet:

```bash
git push -u origin HEAD
```

**Create** (no existing PR):

```bash
gh pr create --base main --title "type(scope): summary" --body "$(cat <<'EOF'
## Proposal
Why these changes were made: the problem or decision. Not how.

## Changes
- High-level change drawn from the branch commits
- Second bounded change

## Test plan
- How a reviewer verifies this (commands or flows actually run)

## Breaking changes
None
EOF
)"
```

Include an Issue section only when step 3 found one:

```markdown
## Issue
Closes #123
```

**Update** (PR already exists). Refresh title and body from the current commit list so the PR still matches the branch:

```bash
gh pr edit <number> --title "type(scope): summary" --body "$(cat <<'EOF'
## Proposal
Why these changes were made: the problem or decision. Not how.

## Changes
- High-level change drawn from the branch commits
- Second bounded change

## Test plan
- How a reviewer verifies this (commands or flows actually run)

## Breaking changes
None
EOF
)"
```

Then print the URL:

```bash
gh pr view --json url --jq .url
```
