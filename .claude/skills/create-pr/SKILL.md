---
name: create-pr
description: >-
  Create or update a GitHub pull request with the GitHub CLI: read branch
  commits, write title and body, target the default branch. Use when the user
  asks to create, open, update, or refresh a PR or MR.
disable-model-invocation: true
---

# Create PR

Prefer **`gh`** over the GitHub MCP. Reach for the MCP only when `gh` can't do the job.

**Safety:** never update git config, skip hooks, or force-push the base branch.

**One PR per branch.** Before creating, check whether the branch already has one. If it does, update that PR's title and body. Don't ask, and don't open a second one.

The branch commits are the source of truth for the PR body. They already say what changed and why. Read all of them; use the diff only to clarify an ambiguous message, never as the primary input.

## Workflow

### 1. Get the branch ready

```bash
git status
git fetch origin
git branch --show-current
BASE=$(gh repo view --json defaultBranchRef --jq .defaultBranchRef.name)
```

**Working tree dirty?** Commit it first with `/git-commit`, which partitions the changes and creates the topic branch if you're on the base branch. A PR that omits finished work on the branch is wrong.

**On the base branch with commits already on top of it?** Stop and ask. Relocating them is the user's call.

### 2. Read the commits

```bash
git log --format='%h %s%n%b' "origin/$BASE..HEAD"
```

If a message is ambiguous:

```bash
git diff "origin/$BASE...HEAD"
```

Fill the template in step 4 from these commits. Don't look for a repo PR template. Don't dump file paths.

### 3. Check for an existing PR

```bash
gh pr view --json number,url,title
```

Non-zero exit means no open PR for this branch: create it. Otherwise: update it.

### 4. Push, then create or update

Push if the branch isn't on origin yet:

```bash
git push -u origin HEAD
```

Write the body once, then use it for either path:

```bash
BODY=$(cat <<'EOF'
## Proposal
Why these changes were made: the problem or the decision. Not how.

## Changes
- High-level change drawn from the branch commits
- Second bounded change

## Test plan
- How a reviewer verifies this (commands or flows actually run)

## Breaking changes
None
EOF
)

# No existing PR:
gh pr create --base "$BASE" --title "<title>" --body "$BODY"

# Existing PR — refresh it so it still matches the branch:
gh pr edit <number> --title "<title>" --body "$BODY"
```

Return the PR URL when done:

```bash
gh pr view --json url --jq .url
```

## Title

Conventional Commits, same as `/git-commit`: `type(scope): imperative summary`. One line summarizing the branch as a whole, not a restatement of the newest commit.

## Breaking changes

Read them off the commits, don't assume. A commit marked `type(scope)!:` or carrying a `BREAKING CHANGE:` trailer belongs in that section, stated as what callers must change. Write `None` only when no commit is marked.

## Issue links

Optional. Link an issue only when the user named one or a commit already carries `Closes #N` / `Refs #N`. Never search GitHub for a plausible match, and never invent a link.

`Closes #N` if this PR finishes the issue, `Refs #N` if it's related but unfinished. Add the section only when one applies:

```markdown
## Issue
Closes #123
```

Confirm a named issue exists with `gh issue view <N>`. Don't run `gh issue close` — `Closes #N` in the body handles it on merge.

## Drafts

Add `--draft` when the user asks for one or calls the work WIP. Mark it ready later with `gh pr ready <number>`.
