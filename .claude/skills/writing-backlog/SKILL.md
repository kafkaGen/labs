---
name: writing-backlog
description: Use when the user asks to write, change, or review a feature backlog, points at docs/backlog/, wants to plan an area of a project as features to build one at a time, asks what is ready or what to build next, or is about to start or finish an OpenSpec change for a backlog feature; also when a plan produces PRs too big to review.
disable-model-invocation: true
---

# Writing a backlog

## What a backlog is

One area of a project, one file, under `docs/backlog/`. An area is one part of the vision, a subsystem or a user-facing capability, big enough to need several features. The file lists every feature you want in that area, with its status and what it waits on, so you can pick one, build it as one OpenSpec change and one PR, and see what is left.

It holds the target and the progress together. The end state lives in the features; what is built lives in their status. It is not a spec: a feature says what works once it is built, and the spec for that feature settles how, with acceptance criteria, when it is picked. It is not the vision either: why the project exists, what it builds, and where its scope ends are already in `docs/vision.md`, and the backlog points at them instead of restating them.

## Which mode you are in

| The user | Mode |
| --- | --- |
| Names an area with no file under `docs/backlog/` | **Write** a new backlog |
| Adds, changes, splits, drops, or rethinks features | **Update** it |
| Asks what is ready, what is left, or what can run in parallel | **Report** from it |
| Starts building a feature | **Pick** it |
| Has merged and archived a feature's change | **Close** it |

## Writing it

1. **Orient.** Read `docs/vision.md`, `docs/architecture.md`, `docs/adr/`, and the other backlogs. Never ask for something you can read yourself.
2. **Collect.** Ask the user to dump everything they want in this area, in any order. Write each idea down as one line. Do not refine yet.
3. **Cut features.** Turn the lines into features using the sizing rules below. Feature 1 is the walking skeleton. Every idea lands in a feature, in Rules, in Open decisions, or as a `dropped` feature with its reason. An idea that is already-decided mechanism, such as a module name or a library, goes to `docs/architecture.md` or an ADR instead; list each one in the review so nothing disappears silently. An idea that belongs to another area goes to that area's backlog; if there is none, say so and leave it out.
4. **Grill, briefly.** **REQUIRED SUB-SKILL:** use `grilling`, on *what* and *in which order*, never on *how*. Stop after two or three rounds, even if `grilling` would go on: what is missing, what contradicts, what each feature waits on, which features are really one.
5. **Draft** from [`reference/BACKLOG_TEMPLATE.md`](reference/BACKLOG_TEMPLATE.md). Name domain concepts the way the vision and other backlogs already do.
6. **Review together** in one pass, naming weak spots yourself: a feature nobody could demonstrate, a feature over the size budget, a line that describes the mechanism, a dependency that is really just an order preference.
7. **Save** to `docs/backlog/<area>.md`, kebab-case, and say the path.
8. **Check for ADRs.** A dropped direction or a settled rule is often a decision. **REQUIRED SUB-SKILL:** use `writing-adrs`, which asks before writing anything.

## Sizing a feature

A feature is one OpenSpec change, one PR, one review sitting.

- **Demonstrable on its own.** Its "Done when" line names something a person can run or watch. "The config loader", "the data model", or "the API client" alone fail this test: they are layers, and each one ships inside the first feature that needs it.
- **Feature 1 is the walking skeleton:** the thinnest path that works end to end, with a stub where depth comes later. It holds only what the happy path cannot run without. Error handling, limits, caching, and configuration beyond the defaults each come later, as features of their own. Every later feature adds depth to a working system. None finishes a half-built layer.
- **Around 400 lines of source or fewer**, tests not counted. If you expect more, split it.
- **Named in five words or fewer.** A name that needs "and" is two features.
- **Too small:** it cannot be demonstrated without another feature, or it is a few dozen lines that share a demo with a neighbour. Merge them.

Tests, docs updates, and settings fields are part of every feature's own work, never features of their own.

## Writing a feature

Each feature has three parts, in this order:

- **One to three sentences** on what works once it is built, as behaviour the user sees.
- **Requirement lines**, only for product choices the user made: a default, a limit, a rule. "Uploads are capped at 10 MB by default" is a requirement. "Check the size in a middleware" is the spec's.
- **Done when:** one or two observable checks. "Uploading an 11 MB file is refused with a message naming the limit."

The wording test for every line: if the implementation changed, would this line change? Then it is mechanism. Rewrite it as the result, or leave it to the spec. A question about how goes in the feature as `Open: ...`.

## Status and dependencies

Status and dependencies live only in the index table. Feature sections never repeat them.

| Status | Means |
| --- | --- |
| `todo` | Wanted, not started |
| `building` | An OpenSpec change exists for it |
| `done` | Its PR merged and its change is archived |
| `dropped` | Not building it; its section says why and when |

`Depends on` lists feature IDs (`F2`) and open-decision IDs (`D1`). List a dependency only when the feature cannot be built or demonstrated without it, never because one order feels nicer. A feature is **ready** when it is `todo`, every feature it depends on is `done`, and every decision it names is settled. Ready is worked out on each report, never stored.

IDs are never reused or renumbered. A done or dropped feature stays in the file.

## Rules and open decisions

- **Rules** are product rules that hold from F1 on and that every feature keeps: "Only calls to external services retry." Something a feature introduces, such as a size limit, is that feature's requirement line, and later features keep it because the code and the specs already do.
- **Open decisions** (`D1`, `D2`, ...) are product or scope questions a feature waits on. Each names the features it blocks. Once settled, the decision moves to an ADR, via `writing-adrs`, or into a requirement line, and its row is deleted. A how-question that only one feature's spec needs is an `Open:` line in that feature, not a decision.

## Updating it

Only because the user asked. If you notice the backlog no longer matches the code while doing other work, say so and stop.

- **New idea:** add a feature with the next ID, sized by the rules above.
- **Too big:** split it into new IDs and mark the original `dropped`, "split into F12, F13".
- **Changed mind about a done feature:** never edit it. Add a new feature whose name says what changes and whose first line is `Revises F3.`
- **Changed mind about a todo feature:** edit it in place. If the change turns it into its opposite, mark it `dropped` and record the new direction as a rule or a new feature.
- **No longer wanted:** mark it `dropped` and give the reason and the date in its section.
- Show what changed, then save once the user confirms.

## Reporting from it

Give: the index as it stands, the ready features, which ready features can run in parallel because none depends on another, and what each open decision blocks. Read `docs/architecture.md` and the code, and flag ready features that will likely edit the same module: they can still run in parallel, but one of them will rebase onto the other. Nothing more.

## Picking a feature

1. Check it is ready. If not, say what it waits on and stop.
2. Set it to `building` and put the change name in the index: `f<id>-<slug>`, such as `f3-upload-size-limit`.
3. **REQUIRED SUB-SKILL:** use `openspec-propose`, handing it the feature section, the area's Rules, and the vision's scope. The proposal opens with `Implements: F3 of docs/backlog/<area>.md`, and turns the feature into acceptance criteria and a design.

Several ready features with no dependency between them can be picked together: one change each, built in parallel.

## Closing a feature

After the PR merges and the change is archived, set the feature to `done`. Change nothing else. If the spec departed from a requirement line, it said so in its own proposal; the backlog line changes only when the user asks.

## What a backlog may not do

- **Pick the mechanism.** No modules, libraries, schemas, or endpoints. A name the user's domain already defines, such as a status or an event, is fine when it is the behaviour itself; the wording test decides.
- **Write acceptance criteria.** Each feature's spec writes them when it is picked, after the earlier features have taught you something.
- **Do the research.** Look a fact up only when it decides scope, and write down the consequence, not the finding.
- **Plan.** No estimates, no dates. The dependency graph is the only ordering.
- **Explain how to use itself.** That lives in this skill, not in each file.

## What belongs elsewhere

- Why the project exists, what it builds, its scope and non-goals: `docs/vision.md`, via `writing-vision`.
- The system's shape: `docs/architecture.md`, via `writing-architecture`.
- A decision with a real trade-off: `docs/adr/`, via `writing-adrs`.
- Acceptance criteria, design, and tasks for one feature: an OpenSpec change, via `openspec-propose`.
