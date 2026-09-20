---
name: domain-modeling
description: Build and sharpen a project's domain model. Use when discussing codebase terminology, writing or editing a CONTEXT.md, or recording or editing an ADR.
---

# Domain Modeling

Actively build and sharpen the project's domain model as you design. This is the *active* discipline: challenging terms, inventing edge-case scenarios, and writing the glossary and decisions down the moment they crystallise. (Merely *reading* `CONTEXT.md` for vocabulary is not this skill: that's a one-line habit any skill can do. This skill is for when you're changing the model, not just consuming it.)

## Find the context before you write

This repo is a monorepo. Each project under `packages/` is its own context with its own glossary and its own decisions. **Before creating or editing any `CONTEXT.md` or ADR, decide which context the term or decision belongs to.**

1. Name the project under `packages/` it belongs to. The files being edited, the topic of the conversation, or the user naming it are each enough to decide.
2. If it belongs to a project, write inside that package and nowhere else: `packages/<project>/CONTEXT.md`, `packages/<project>/docs/adr/`.
3. Write at the repo root only when the term or decision binds every package: shared tooling, the build, cross-package conventions. A term that a single project owns never goes to the root.
4. If two packages could plausibly own it, ask which one. Never copy the same term into two glossaries: one term, one home.
5. If the work belongs to a project that doesn't exist under `packages/` yet, say so and settle where it lives before writing.

## File structure

```
/
├── CONTEXT.md                  ← repo-wide vocabulary only (rare)
├── docs/adr/                   ← decisions binding every package
│   └── 0001-uv-workspace.md
└── packages/
    ├── distillery/
    │   ├── CONTEXT.md          ← this project's glossary
    │   ├── docs/adr/           ← this project's decisions
    │   │   └── 0001-telegram-as-first-source.md
    │   └── src/
    └── <project>/
```

ADRs are numbered per directory: each `docs/adr/` starts at `0001` independently of the others.

An integration between two packages belongs to neither glossary. Record it as an ADR at the repo root.

Create files lazily: only when you have something to write. If the package has no `CONTEXT.md`, create one when the first term is resolved. If it has no `docs/adr/`, create it when the first ADR is needed.

## During the session

### Challenge against the glossary

When the user uses a term that conflicts with the existing language in the context's `CONTEXT.md`, call it out immediately. "Your glossary defines 'cancellation' as X, but you seem to mean Y. Which is it?"

### Sharpen fuzzy language

When the user uses vague or overloaded terms, propose a precise canonical term. "You're saying 'account': do you mean the Customer or the User? Those are different things."

### Discuss concrete scenarios

When domain relationships are being discussed, stress-test them with specific scenarios. Invent scenarios that probe edge cases and force the user to be precise about the boundaries between concepts.

### Cross-reference with code

When the user states how something works, check whether the code agrees. Read that package's `src/`, not the whole repo: a term means what it means inside its own context. If you find a contradiction, surface it: "Your code cancels entire Orders, but you just said partial cancellation is possible. Which is right?"

### Update CONTEXT.md inline

When a term is resolved, update the owning context's `CONTEXT.md` right there. Don't batch these up: capture them as they happen. Use the format in [CONTEXT-FORMAT.md](./CONTEXT-FORMAT.md).

`CONTEXT.md` should be totally devoid of implementation details. Do not treat `CONTEXT.md` as a spec, a scratch pad, or a repository for implementation decisions. It is a glossary and nothing else.

### Offer ADRs sparingly

Only offer to create an ADR when all three are true:

1. **Hard to reverse**: the cost of changing your mind later is meaningful
2. **Surprising without context**: a future reader will wonder "why did they do it this way?"
3. **The result of a real trade-off**: there were genuine alternatives and you picked one for specific reasons

If any of the three is missing, skip the ADR. Use the format in [ADR-FORMAT.md](./ADR-FORMAT.md).
