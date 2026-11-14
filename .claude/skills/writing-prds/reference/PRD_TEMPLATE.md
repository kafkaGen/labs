<!--
One feature, one file: docs/prd/NNNN-kebab-slug.md, four digits, next after the highest in the directory.
A new PRD is always Draft.
Every line under a phase is one idea: what the feature does, or a product choice. Never how.
No acceptance criteria: each phase's spec writes them.
An answer you couldn't verify still goes in its line, marked "Assumed: ...".
A question about how goes under its phase as "Open: ...", for the spec.
Delete a section only if it genuinely doesn't apply, and say in its place why.
-->

# PRD: <feature name>

**Status:** Draft
**In one line:** <what this feature is>
**Serves:** <the goal from [`../vision.md`](../vision.md) this takes on>

## Why this feature

What is missing or broken without it, and why it is worth building now. Two or three sentences; the project's own problem is already in the vision.

## What we build

The capability and who uses it, in a paragraph. Stated as behaviour, not as the thing that delivers it.

## Across every phase

Rules that hold unchanged in every phase. Delete this section when there are none.

- ...

## Phases

In build order. Each phase is one spec. Phase 1 is the thinnest path that works end to end.

### Phase 1: <short name>

Once built: <one sentence saying what works, and who can see it working>.

- <requirement>
- <requirement>
- Open: <a how-question for the spec>

### Phase 2: <short name>

Once built: ...

- ...

## Out of scope

Deferred, each with what would bring it back. A direction ruled out forever is a non-goal and belongs to the vision.

- ...

## Success criteria

How you know the feature worked once it is in use. Each one has an observable signal, even an informal one.

- ...

## Approach note

Optional, and binding on nobody. Constraints this feature inherits from the vision, the architecture, or an ADR. Delete this section if there is nothing to point at.
