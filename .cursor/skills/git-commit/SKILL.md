---
name: git-commit
description: Turn the current working-tree changes into well-scoped, well-described git commits and push them. Use when the user asks to commit, save progress, or push, or whenever completed work is sitting uncommitted and a commit is warranted.
---

# Git Commit

## Workflow

1. **Inspect what changed.** Run `git status`, `git diff`, and `git diff --staged` (in parallel). For new/untracked files whose purpose isn't obvious from a diff, open them to understand intent. If the tree is clean, say so and stop.
2. **Partition into logical commits.** A logical commit is the smallest set of file changes that stands on its own — one feature, one fix, one refactor, one doc update, one config tweak, one test addition. Changes belonging to different purposes go in different commits, even within the same file (in that case, commit with the dominant purpose and note the mixing to the user). Never use `git add -p`/`-i` for splitting; select whole files per commit instead.
3. **Stage and commit one partition at a time**: `git add <files for this partition>`, then commit using the message format below. Confirm with `git status` that only the intended partition was captured before moving to the next.
4. **Repeat step 3** until every change is committed.
5. **Push everything**: `git push -u origin HEAD`, after telling the user which branch it's going to. If there's no configured remote, stop and say so instead of guessing one.

## Message format

Detect the convention already in use with `git log -8 --oneline`, and match it. Two conventions are supported; default to the tagged style unless the log already uses Conventional Commits.

**Tagged style (default):**
```
[type] (scope) Imperative title, ~50 chars

One-sentence expansion of the title.

A short paragraph on why this change was needed and what it now enables. Stay
high-level — the diff already shows what/how; the message should carry the
intent that isn't visible in the diff.

Closes #123
```

**Conventional Commits style** (use only if the repo's history already does):
```
type(scope): imperative summary

Same why-focused body as above.

BREAKING CHANGE: what callers must change.
```

Field rules, both styles:
- **type/tag** — one of `feature`, `fix bug`, `refactor`, `doc`, `config`, `test`. Conventional Commits equivalents: `feat`, `fix`, `refactor`, `docs`, `chore`, `test`.
- **scope** — the module/area touched. Include only when it disambiguates; omit for small or repo-wide changes.
- **breaking changes** — tagged style: append `[breaking]` after the type, e.g. `[refactor] [breaking]`. Conventional style: append `!` after the scope, e.g. `refactor(api)!`, and add a trailing `BREAKING CHANGE:` line. Either way, the body must say what callers need to change.
- **footer** — an optional trailing `Closes #123` / `Refs #123` line when a known issue/ticket applies. Leave it out otherwise.
- **body** — explain motivation and impact, not implementation. Never restate the diff line-by-line.

Write multi-line messages via HEREDOC so quoting is safe:
```bash
git commit -m "$(cat <<'EOF'
[feature] (auth) Add authenticated sessions

Keep users signed in across requests.

Repeated logins were breaking longer workflows. A durable session identity
lets upcoming features assume a signed-in actor without re-authenticating.
EOF
)"
```

## Guardrails

- Never pass `--no-verify`, force-push, or touch git config.
- Never stage or commit secrets (`.env`, credentials, private keys).
- If a pre-commit hook rejects a commit, fix the issue and re-commit; don't bypass the hook.
- Only amend an existing commit if the user asks for it and it hasn't been pushed yet.

## Examples

**Small fix, tagged style:**
```
[fix bug] (checkout) Stop double-charging on retried payments

Prevent a retried payment request from being charged twice.

The retry path skipped the idempotency check the first attempt used,
so network retries could charge a customer more than once.
```

**Breaking change, Conventional Commits style:**
```
refactor(search)!: replace positional filter args with a query object

Positional filter arguments couldn't absorb new search criteria without
breaking every call site. A single query object lets filtering grow without
further signature churn.

BREAKING CHANGE: filter(a, b, c) is now filter({ a, b, c }).
```
