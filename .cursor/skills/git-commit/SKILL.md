---
name: git-commit
description: Turn the current working-tree changes into well-scoped, well-described git commits and push them. Use when the user asks to commit, save progress, or push, or whenever completed work is sitting uncommitted and a commit is warranted.
---

# Git Commit

## Workflow

### 1. Inspect what changed

Run `git status`, `git diff`, and `git diff --staged` in parallel. Open new or untracked files whose purpose a diff doesn't reveal. If the tree is clean, say so and stop.

### 2. Partition into logical commits

A logical commit is the smallest set of file changes that stands on its own: one feature, one fix, one refactor, one doc update, one config tweak, one test addition. Different purposes go in different commits even within one file — in that case commit under the dominant purpose and tell the user it's mixed.

Select whole files per commit. Never split with `git add -p` or `git add -i`.

### 3. Branch if you're on the default branch

```bash
git branch --show-current
git symbolic-ref --short refs/remotes/origin/HEAD 2>/dev/null   # e.g. origin/main
```

On the default branch, create a topic branch before the first commit, named for the dominant partition from step 2:

```bash
git switch -c <type>/<short-name>    # feature/auth-sessions, fix/retry-double-charge
```

Already on a topic branch: continue.

### 4. Stage and commit, one partition at a time

```bash
git add <files for this partition>
git commit -m "..."      # format below
git status               # confirm only the intended partition was captured
```

Repeat until every change is committed.

### 5. Push

Tell the user which branch it's going to, then:

```bash
git push -u origin HEAD
```

No configured remote: stop and say so rather than guessing one.

## Message format

Conventional Commits, always — regardless of what the existing history looks like.

```
type(scope): imperative summary, ~50 chars

One-sentence expansion of the summary.

A short paragraph on why this change was needed and what it now enables. Stay
high-level — the diff already shows what and how; the message carries the
intent that isn't visible in the diff.

Closes #123
Co-authored-by: Cursor <cursor@cursor.com>
```

Field rules:

- **type** — one of `feat`, `fix`, `refactor`, `docs`, `chore`, `test`.
- **scope** — the module or area touched. Include it only when it disambiguates; omit for small or repo-wide changes.
- **body** — motivation and impact, not implementation. Never restate the diff line by line. Let the body scale with the change: a self-evident commit (typo, version bump, formatter run) can be a title alone. If you can't name a why beyond what the title says, don't pad one.
- **breaking changes** — append `!` after the scope, e.g. `refactor(api)!:`, and add a `BREAKING CHANGE:` line to the trailer block. The body must say what callers need to change.
- **trailers** — `Closes #123` / `Refs #123` when a known issue applies, omitted otherwise. End every commit with `Co-authored-by: Cursor <cursor@cursor.com>`. Trailers go in one block at the end, no blank lines between them.

Write multi-line messages via HEREDOC so quoting is safe:

```bash
git commit -m "$(cat <<'EOF'
feat(auth): add authenticated sessions

Keep users signed in across requests.

Repeated logins were breaking longer workflows. A durable session identity
lets upcoming features assume a signed-in actor without re-authenticating.

Co-authored-by: Cursor <cursor@cursor.com>
EOF
)"
```

## Guardrails

- Never pass `--no-verify`, force-push, or touch git config.
- Never stage or commit secrets (`.env`, credentials, private keys).
- A pre-commit hook rejects a commit: fix the issue and re-commit. Don't bypass the hook.
- Amend an existing commit only when the user asks and it hasn't been pushed.

## Examples

**Small fix:**

```
fix(checkout): stop double-charging on retried payments

Prevent a retried payment request from being charged twice.

The retry path skipped the idempotency check the first attempt used,
so network retries could charge a customer more than once.

Co-authored-by: Cursor <cursor@cursor.com>
```

**Breaking change:**

```
refactor(search)!: replace positional filter args with a query object

Positional filter arguments couldn't absorb new search criteria without
breaking every call site. A single query object lets filtering grow without
further signature churn.

BREAKING CHANGE: filter(a, b, c) is now filter({ a, b, c }).

Co-authored-by: Cursor <cursor@cursor.com>
```
