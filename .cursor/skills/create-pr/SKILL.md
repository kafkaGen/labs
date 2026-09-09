---
name: create-pr
description: >-
  Create or update a GitHub pull request via GitHub MCP: inspect branch commits,
  search and link related issues, write title and body, target main. Use when the
  user asks to create, open, update, or refresh a PR or MR.
---

# Create PR

Use **GitHub MCP**, not `gh`. Inspect the GitHub namespace schema before calling. Never open a PR from `main`. If still on `main`, stop — git-commit creates the topic branch on first commit.

**Safety:** never update git config, skip hooks, or force-push `main`.

## Workflow

1. **Inspect** — owner/repo from `git remote get-url origin`. Know every change on this branch:

```bash
git status
git fetch origin
git log --format='%h %s%n%b' origin/main..HEAD
git diff origin/main...HEAD
```

Fill the body template below from those commits. Do not look for a repo PR template.

2. **Existing PR** — `list_pull_requests` (`owner`, `repo`, `state: open`, `head: <owner>:<branch>`, `base: main`). If one exists, `update_pull_request` instead of create.

3. **Issues** — GitHub MCP:

- `#N` in commits or chat → `issue_read` (`method: get`, `owner`, `repo`, `issue_number`)
- else `search_issues` (`query` = short purpose from commits, `owner`, `repo`)
- still nothing → `list_issues` (`owner`, `repo`, `state: OPEN`)

If this PR finishes the work: `Closes #N` in the **PR body**. Related but unfinished: `Refs #N`. Else `None`. Do not close via `issue_write`.

4. **Create or update** — `base` is always `main`. Title: `type(scope): summary` (same as git-commit). **Always** pass `owner`, `repo`, `title`, `head`, `base`.

`create_pull_request`: `owner`, `repo`, `title`, `head` (current branch), `base: main`, `body`.

`update_pull_request`: `owner`, `repo`, `pullNumber`, `title`, `body`.

Push first if the branch is not on origin (`git push -u origin HEAD`). Return the PR URL.

## PR body template

```markdown
## Title
type(scope): short imperative summary

## Issue
Closes #123
<!-- or Refs #123 / None -->

## Proposal
Why these changes were made: the problem or decision. Not how.

## Changes
- High-level change drawn from the branch commits
- Second bounded change

## Test plan
- How a reviewer verifies this (commands or flows actually run)

## Breaking changes
None
```

Fill from the commit list. Do not dump file paths. Keep headings.
