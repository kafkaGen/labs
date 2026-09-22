---
name: writing-prds
description: Use when the user asks to write, draft, or change a PRD or a feature requirements doc, or points at docs/prd/; also when a feature is large enough to need several specs and nothing yet states what it must do.
disable-model-invocation: true
---

# Writing PRDs

## What a PRD is

One feature, one file, under `docs/prd/`. It takes one goal from the vision and states what that feature must do, how you check it got built, and how you check it worked. Its use cases are what the specs get cut from.

It is not a spec. A spec finds the solution, and does whatever research that takes. A PRD states the problem at feature scale and leaves the mechanism open.

It is not the vision either. The vision covers the whole project; a PRD covers one goal from it.

## When it earns its place

A PRD is for a feature big enough that several specs will be written against it. One use case is not a PRD: brainstorm the spec instead and say so.

## Which mode you are in

- No file for this feature under `docs/prd/`: **write it**.
- It exists: **update it**, and only because the user asked.

## Writing it

1. **Orient.** Read `docs/vision.md` for the goal this feature serves, `docs/architecture.md` for the limits it lands in, and the existing PRDs under `docs/prd/`. Never ask for something you can read yourself.

2. **Grill.** **REQUIRED SUB-SKILL:** use `grilling`. The design tree, in dependency order: why this feature and why now, what we build, use cases, the acceptance criteria for each use case, cross-cutting functional requirements, in scope, out of scope, success criteria, non-functional requirements. Later branches lean on earlier ones.

   An answer you could not verify still goes in the section it belongs to, marked `Assumed: ...`. Assumptions never get a list of their own.

3. **Draft** from [`reference/PRD_TEMPLATE.md`](reference/PRD_TEMPLATE.md). Name each domain concept the way the vision and the earlier PRDs already name it. The specs are cut from this file, so a word invented here spreads.

4. **Review together**, section by section. Name the weak spots yourself: a use case that is really one step inside another, an acceptance criterion nobody could check, a success criterion that restates the acceptance criteria, a non-functional requirement with no number in it.

5. **Save** under the name the next section gives it, and say the path.

6. **Check for ADRs.** A scoping session settles what is deliberately not built, and that is often a decision rather than a scope line. **REQUIRED SUB-SKILL:** use `writing-adrs`, which asks before writing anything.

## Numbering and naming

`docs/prd/NNNN-kebab-slug.md`. Four digits, zero padded. Read the directory, take the highest existing number, add one. Create `docs/prd/` when you write the first one and not before.

The slug is a short version of the feature name: `0003-digest-action-requests.md`. Cite a PRD in prose as PRD-0003, and link it relatively when the reader is in another file under `docs/`.

The numbers are the order the product was built in, so they are never reused and never renumbered.

## Status

A new PRD is `Draft`, always, whatever the session settled. It becomes `Building` when work starts against it and `Shipped` once every use case in it is built, and neither of those happens in the session that wrote it.

## Sizing a use case

A use case is one goal an actor completes in one sitting. That size is the whole point: it is what one spec is cut from.

The test: **does the actor's day depend on how many of these they do?** "Log in" fails, so it is a step inside another use case. "Register a customer" passes. If you wrote the flow out it would run three to nine steps.

- Too small: it cannot be demonstrated on its own, or it only exists to serve another use case. Fold it in.
- Too big: it spans several sittings, or its acceptance criteria would not all ship together. Split it.
- Three to eight per PRD is normal. One means you want a spec, not a PRD.

Order them the way you would explain the feature to someone, not by priority.

## Writing acceptance criteria

Plain sentences under the use case they belong to. One condition each, observable from outside the system.

- **Rejection-worthy only.** If you would accept the feature without it, it is not a criterion.
- **Cover the failure too.** For each use case, ask what happens when the thing it depends on is missing, refused, or wrong, and write that line. Unstated failure behaviour is where features get sent back.
- **The wording test:** if the implementation changed, would this line have to change? Then it describes the mechanism, and needs rewriting as the result.

No Given/When/Then. At feature scale it collapses into a business rule wearing a scenario's clothes, which reads formal and checks nothing.

## Keeping the sections apart

These collapse into each other if you let them.

| Section | Answers | Not this |
|---|---|---|
| Why this feature | What is missing now, and which vision goal this takes on | The project's problem restated |
| What we build | The capability, in a paragraph | The mechanism that delivers it |
| Use case | One goal an actor completes in one sitting | A step inside another use case, or a capability listed for completeness |
| Acceptance criteria | What you check to call that use case built | The test plan, or the implementation |
| Functional requirement | A rule that holds across use cases | A criterion that belongs to one of them |
| In scope | The boundary the use cases do not name | The use cases rewritten as nouns |
| Out of scope | Deferred, with what brings it back | A direction ruled out forever, which is the vision's non-goal |
| Success criteria | How you know it worked once people use it | The acceptance criteria in other words |
| Non-functional requirement | A quality this feature changes, with a number, holding across the feature | Every quality attribute listed for completeness, or a number that belongs to one use case and is that use case's criterion |

## What a PRD may not do

- **Do the research.** A question that needs a lookup to answer is the spec's, and the answer never lands here. Look a fact up yourself only when it decides whether something is in or out of scope, and then write down the consequence for scope, not the findings.
- **Pick the mechanism.** No components, no libraries, no schema, no endpoints. A constraint the feature inherits from the vision or the architecture is not a mechanism: it goes in the approach note, which binds nobody.
- **List a quality without a measure.** "Fast", "secure", "reliable" are not requirements. A non-functional requirement states what, under which conditions, and to what number, and it only appears when this feature changes the answer.
- **Plan.** No estimates, no dates, no task breakdown, no ordering of the specs.

## Updating it

The user asks for the change. If you notice the PRD no longer matches reality while doing other work, say so and stop.

- Grill only the sections the request touches, plus the ones that depend on them. A new use case ripples into scope and success criteria; a changed number rarely ripples anywhere.
- Leave every other section exactly as it was.
- Show what changed, then save once the user confirms.

## What belongs elsewhere

- The project's problem, users, and non-goals: `docs/vision.md`.
- The system's shape, built or intended: `docs/architecture.md`, via `writing-architecture`.
- A decision with a real trade-off behind it: an ADR under `docs/adr/`, via `writing-adrs`.
- The solution, the research behind it, and the files it touches: the spec, via `brainstorming` and then `writing-plans`.
