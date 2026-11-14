---
name: writing-vision
description: Use when the user asks to write, draft, redo, or change a project vision or intent doc, or points at docs/vision.md; also when a project's problem, scope, or definition of success is unsettled and a PRD or architecture doc is about to be written on top of it.
disable-model-invocation: true
---

# Writing a project vision

## What a vision is

The vision states a project's intent: the problem, the goal, who it is for, what is in and out, and how you would know it worked. It sits at the top of the doc stack. A PRD takes one goal from it; specs break a PRD down.

It is not a plan, an architecture, or a feature list. One page. If a section needs more than a short paragraph or a handful of bullets, that detail belongs in a PRD.

## Which mode you are in

- `docs/vision.md` does not exist: **write it**.
- It exists: **update it**, and only because the user asked.

## Writing it

1. **Orient.** Read what already exists: `README.md`, `docs/`, the code. Never ask for something you can read yourself.

2. **Grill.** **REQUIRED SUB-SKILL:** use `grilling`. The design tree, in dependency order: problem, goal, learning objectives, users, core use cases, in scope, out of scope, non-goals, success criteria, constraints. Later branches lean on earlier ones.

   Do not push for user interviews or market validation the user has not already done. Where you would need one, write the best answer into its own section marked `Assumed: ...` and move on. Assumptions live in the section they belong to, never in a list of their own.

3. **Draft** from [`reference/VISION_TEMPLATE.md`](reference/VISION_TEMPLATE.md).

4. **Review together**, section by section. Name the weak spots yourself rather than waiting: a goal that restates the problem, a success criterion nobody could check, a non-goal that is really out of scope.

5. **Save** to `docs/vision.md` and say the path.

6. **Check for ADRs.** If the grill settled a constraint or ruled a direction out against a live alternative, that is a decision, not a vision line. **REQUIRED SUB-SKILL:** use `writing-adrs`, which asks before writing anything. Most vision sessions produce none.

## Updating it

The user asks for the change. If you notice the vision no longer matches reality while doing other work, say so and stop. Never edit the vision on your own initiative.

- Grill only the sections the request touches, plus the ones that depend on them. A changed goal ripples into success criteria and scope; a changed constraint rarely ripples anywhere.
- Leave every other section exactly as it was.
- Show what changed, then save once the user confirms.

## Keeping the sections apart

These sections collapse into each other if you let them.

| Section | Answers | Not this |
|---|---|---|
| Goal | What is true once this works | The checks that prove it (success criteria) |
| Success criteria | How you would check the goal landed | Another phrasing of the goal |
| Out of scope | Deferred, could plausibly land later | A direction ruled out forever (non-goal) |
| Non-goal | Ruled out even at maturity, on purpose | Something merely not scheduled yet |
| Constraint | A hard limit you cannot move | A preference or a design choice |
| Core use case | A flow you will walk through | A capability listed for completeness |
| In scope | The capability boundary, including what no use case names | The use cases rewritten as nouns |

## What belongs elsewhere

- Tech stack, components, hosting: `docs/architecture.md`.
- A decision with a real trade-off behind it: an ADR under `docs/adr/`, via `writing-adrs`.
- Feature-level requirements for one goal: a PRD under `docs/prd/`, via `writing-prds`.
