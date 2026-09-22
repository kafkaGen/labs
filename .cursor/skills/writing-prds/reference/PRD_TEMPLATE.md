<!--
One feature, one file: docs/prd/NNNN-kebab-slug.md, four digits, next after the highest in the directory.
A new PRD is always Draft.
Every section outside the use cases is a short paragraph or a few bullets;
the use cases are the only part that grows.
Delete a section only if it genuinely doesn't apply, and say in its place why.
An answer you couldn't verify still goes in its section, marked "Assumed: ...".
-->

# PRD: <feature name>

**Status:** Draft
**In one line:** <what this feature is>
**Serves:** <the goal from [`../vision.md`](../vision.md) this takes on>

## Why this feature

What is missing or broken without it, and what people do instead today. Why it is worth building now rather than later. Two or three sentences; the project's own problem is already in the vision.

## What we build

The capability, in a paragraph. What it lets someone do that they cannot do today, stated as behaviour rather than as the thing that delivers it.

## Use cases

One goal an actor completes in one sitting, each with the criteria that say it got built. Ordered the way you would explain the feature, not by priority. Three to eight of them.

### 1. <actor does the thing>

One or two sentences: who, what they do, what they get out of it.

**Acceptance criteria**

- <One observable condition. You would send the work back without it.>
- <What happens when it fails, is refused, or the input is wrong.>

### 2. <actor does the next thing>

...

## Functional requirements

Rules that hold across use cases and belong to no single one: limits, validation, what a state means, what happens on a shared failure. Anything already checked under a use case does not repeat here. Delete this section when there is nothing that crosses.

- ...

## In scope

The capability boundary the use cases do not name: what this feature covers beyond the flows above, and what it takes over from elsewhere.

- ...

## Out of scope

Deferred, each with what would bring it back. A direction ruled out forever is a non-goal and belongs to the vision.

- ...

## Success criteria

How you know the feature worked once it is in use. Each one has an observable signal, even an informal one. Not the acceptance criteria again: those say it got built, these say it mattered.

- ...

## Non-functional requirements

Only the qualities this feature changes, each with a number and the conditions it holds under. A quality the system already commits to elsewhere, and that this feature does not move, gets no line. Delete this section if nothing here changes.

| Quality | Under these conditions | Measure |
|---|---|---|
| <latency, throughput, retention, privacy, cost, ...> | <the load, state, or event it has to hold under> | <the number, and where it is read> |

## Approach note

Optional, and binding on nobody. The direction this looks like it will take, plus any constraint it inherits from the vision, the architecture, or an ADR. The spec decides the mechanism and does the research; this only points. Delete this section if there is nothing to point at.
