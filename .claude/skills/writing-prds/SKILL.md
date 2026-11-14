---
name: writing-prds
description: Use when the user asks to write, draft, or change a PRD or a feature requirements doc, or points at docs/prd/; also when a feature is large enough to need several specs and nothing yet states what it must do.
disable-model-invocation: true
---

# Writing PRDs

## What a PRD is

One feature, one file, under `docs/prd/`. It takes one goal from the vision, collects the requirements for that feature as one-line ideas, and cuts them into phases. Each phase becomes one spec.

It is short on purpose. The spec for a phase is where the detail gets settled: the acceptance criteria, the mechanism, and the research. A PRD that settles those too gets grilled twice and reviewed twice, and its later phases go stale before anyone builds them.

It is not the vision either. The vision covers the whole project; a PRD covers one goal from it.

## When it earns its place

A PRD is for a feature that needs two or more specs. If everything fits in one phase, brainstorm the spec instead and say so.

## Which mode you are in

- No file for this feature under `docs/prd/`: **write it**.
- It exists: **update it**, and only because the user asked.

## Writing it

1. **Orient.** Read `docs/vision.md` for the goal this feature serves, `docs/architecture.md` for the limits it lands in, and the existing PRDs under `docs/prd/`. Never ask for something you can read yourself.

2. **Collect the requirements.** Ask the user to dump everything they want this feature to have, in any order. Write each idea down as one line. Do not refine them yet.

3. **Grill, briefly.** **REQUIRED SUB-SKILL:** use `grilling`. The design tree, in dependency order: why this feature and why now, what we build, which requirements are missing or contradict each other, the phase cut, out of scope, success criteria. Aim for two or three rounds.

   Every question must be about *what* or *when*, never *how*. A question about how belongs to the spec: write it under its phase as `Open: ...` and move on. An answer you could not verify goes in its line, marked `Assumed: ...`.

4. **Draft** from [`reference/PRD_TEMPLATE.md`](reference/PRD_TEMPLATE.md). Name each domain concept the way the vision and the earlier PRDs already name it. The specs are cut from this file, so a word invented here spreads.

5. **Review together** in one pass. Name the weak spots yourself: a line that describes the mechanism, a phase that cannot be demonstrated on its own, a phase too big for one spec, a success criterion that only restates a requirement.

6. **Save** under the name the next section gives it, and say the path.

7. **Check for ADRs.** A scoping session settles what is deliberately not built, and that is often a decision rather than a scope line. **REQUIRED SUB-SKILL:** use `writing-adrs`, which asks before writing anything.

## Numbering and naming

`docs/prd/NNNN-kebab-slug.md`. Four digits, zero padded. Read the directory, take the highest existing number, add one. Create `docs/prd/` when you write the first one and not before.

The slug is a short version of the feature name: `0003-digest-action-requests.md`. Cite a PRD in prose as PRD-0003, and a phase as phase 2 of PRD-0003. Link it relatively when the reader is in another file under `docs/`.

The numbers are the order the product was built in, so they are never reused and never renumbered.

## Status

A new PRD is `Draft`, always, whatever the session settled. It becomes `Building` when the first phase's spec starts and `Shipped` once every phase is built, and neither of those happens in the session that wrote it.

## Writing a requirement line

One line, one idea, stated as what the feature does or a product choice the user made. "A USD cap per request, $0.10 by default" is a requirement. "Retry overloads that arrive mid-stream with backoff" is the spec's.

- **The wording test:** if the implementation changed, would this line have to change? Then it describes the mechanism. Rewrite it as the result, or drop it and let the spec decide.
- **Numbers are fine** when they are the user's choice: a default, a limit, a budget. A number that only follows from an API or a library is a research finding, and belongs to the spec.
- **No acceptance criteria.** The spec writes them, for one phase, when that phase is next. Writing them here for every phase fixes details before the earlier phases have taught you anything.

## Cutting phases

A phase is a slice of the feature that one spec can build and that someone can demonstrate on its own. Each phase opens with one sentence saying what works once it is built.

- **Phase 1 is the thinnest path that works end to end.** Later phases add depth to a working system: limits, resilience, more inputs, more tools. They do not finish half-built layers.
- **Too big:** its requirements would not all ship in one spec, or the demo sentence needs "and" twice. Split it.
- **Too small:** it cannot be demonstrated without the next phase. Merge them.
- Two to six phases is normal. One means you want a spec, not a PRD.

Order phases in build order. A requirement that grows across phases, such as logging, gets a line in each phase that extends it. A rule that holds unchanged in every phase goes under "Across every phase", once.

## Keeping the sections apart

| Section | Answers | Not this |
|---|---|---|
| Why this feature | What is missing now, and which vision goal this takes on | The project's problem restated |
| What we build | The capability and who uses it, in a paragraph | The mechanism that delivers it |
| Across every phase | Rules that hold unchanged in every phase | A requirement that one phase delivers |
| Phase | One spec's worth of requirements, with what works afterwards | A task list, or a design |
| Out of scope | Deferred, with what brings it back | A direction ruled out forever, which is the vision's non-goal |
| Success criteria | How you know it worked once people use it | The requirements in other words |

## What a PRD may not do

- **Do the research.** A question that needs a lookup to answer is the spec's, and the answer never lands here. Look a fact up yourself only when it decides whether something is in or out of scope, and then write down the consequence for scope, not the findings.
- **Pick the mechanism.** No components, no libraries, no schema, no endpoints, no API details. A constraint the feature inherits from the vision, the architecture, or an ADR is not a mechanism: it goes in the approach note, which binds nobody.
- **Write acceptance criteria.** Those belong to each phase's spec.
- **Plan.** No estimates, no dates, no task breakdown. Phase order is the only ordering it states.

## Where the spec takes over

The spec for a phase starts with `Implements: phase N of PRD-NNNN`. It turns that phase's lines and its `Open:` questions into acceptance criteria and a design, and runs the only detailed grilling. When it drops or changes a requirement line, it says so in its own deviations section. The PRD changes only if the user asks.

## Updating it

The user asks for the change. If you notice the PRD no longer matches reality while doing other work, say so and stop.

- Grill only what the request touches, plus what depends on it. A new requirement may move between phases; a changed number rarely ripples anywhere.
- Leave every other section exactly as it was.
- Never change a phase that is already built. Add a new phase instead.
- Show what changed, then save once the user confirms.

## What belongs elsewhere

- The project's problem, users, and non-goals: `docs/vision.md`.
- The system's shape, built or intended: `docs/architecture.md`, via `writing-architecture`.
- A decision with a real trade-off behind it: an ADR under `docs/adr/`, via `writing-adrs`.
- The acceptance criteria, the solution, the research behind it, and the files it touches: the spec, via `brainstorming` and then `writing-plans`.
