---
name: writing-architecture
description: Use when the user wants to work out or record how a system is put together, asks to write or update docs/architecture.md, or needs a shape settled before code exists; also when implementation has drifted from what the doc says.
---

# Writing an architecture doc

## What the doc is

`docs/architecture.md` is one committed file holding the system's shape: its context, components, flows, stores, dependencies, and the limits it lives inside. You write it before the code to set a direction, then correct it as the code goes its own way.

It is allowed to run ahead of the code. One convention keeps that honest: every component, flow, store, and dependency is marked **Built** or **Planned**. A reader must never have to guess which lines are real, and that is the only thing here worth being strict about.

One architecture, present tense. An alternative that lost belongs in an ADR, not in this file.

## Which mode you are in

- **Design.** No file yet, or a new part of the system to work out. This is most of the skill, and it ends with a doc plus a list of ADR candidates.
- **Update.** Code landed and the doc no longer matches it. Short and mechanical, driven by the diff.

## Design mode

1. **Orient.** Read `docs/vision.md` for the problem, users, scope, and constraints, the PRDs under `docs/prd/` for what the system has to do, and `docs/adr/` for what is already settled. If code exists, read it first using the list below. Never ask for something you can read yourself.

2. **Propose before asking.** Draft a whole shape and put it in front of the user: components, edges, stack. A wrong first proposal is faster to correct than twenty questions, and it gives them something to react to.

3. **Put a second shape next to the first.** Name one materially different way to build this and why it loses: a static artifact instead of a service, one process instead of three, a file instead of a database. If the reason it lost is a constraint rather than an architectural argument, say which constraint, especially when it is a learning goal. An alternative you never showed the user is one you decided for them.

4. **Grill every fork.** **REQUIRED SUB-SKILL:** use `grilling`. Go after the choices that are expensive to undo: where a boundary falls, which component owns which data, what the system does when a dependency is down, what breaks first at ten times the expected size, what a second instance of this would collide with. Where an answer is genuinely forced, write it down and move on. This step is the point of the skill. The document is a by-product of the argument.

5. **Look facts up yourself.** When a fork turns on whether something is possible, a library's limits, an API's terms, a platform's quota, dispatch a subagent to find out. Never ask the user to look it up. Write the answer down with where it came from, and treat it as provisional.

6. **Draft** from [`reference/ARCHITECTURE_TEMPLATE.md`](reference/ARCHITECTURE_TEMPLATE.md), with diagrams from [`reference/MERMAID_DIAGRAMS.md`](reference/MERMAID_DIAGRAMS.md). Mark every line Built or Planned. Where you chose something the user never confirmed, say so on its line rather than letting it read as settled.

7. **Never invent a number.** Throughput, latency, cost, retention, a ceiling: where nothing measures it, state the mechanism and the constant that governs it ("one thread, serial, ten second timeout per call") and leave the figure out. A guessed number is what makes a direction read as a measurement. Cost is the usual trap: "egress is charged per gigabyte, so relaying bytes through the server grows with viewing" is fair, a price per gigabyte is not.

8. **Review together**, section by section, then **save** to `docs/architecture.md` and say the path.

9. **Record the ADRs.** **REQUIRED SUB-SKILL:** use `writing-adrs`. List the decisions **the user made** that are hard to reverse and cost a real alternative, and let them pick which get written. Something you settled on your own is an assumption on its line, not an ADR.

## Update mode

Here the code is the source of truth. Where the doc and the code disagree about something marked Built, the doc is wrong.

An update has two inputs: the diff and the current doc. Source files are not an input; you open one only when step 3 sends you there.

1. **Get the diff.** `git diff <base>...HEAD --stat` for the shape, then the diff itself. If the user named a PR or a branch, that is the range.
2. **Triage against the seven categories below.** If the diff touches none of them, the architecture did not change: say so and stop. Most diffs end here, and that is the point.
3. **Read only what the diff cannot explain.** Where a hunk's structural meaning is clear from the diff, use it. Otherwise open that one file.
4. **Correct only the sections the change touches,** and flip Planned to Built where the code caught up. A new dependency touches external dependencies and probably components. A renamed class touches nothing.
5. **Report each correction** as the difference it fixed: what the doc claimed, what the code does.

An update records drift that already happened. When the user instead wants the doc to lead the code again, that is design mode: say so and switch.

## Where to look in the code

Bounded, in this order. This is also the triage list an update uses.

1. Dependency manifests and lockfiles: what the system is built on and what it calls out to.
2. Entry points: `main`, CLI commands, server bootstrap, scheduled jobs, workers.
3. Module and package layout, top two levels only.
4. Config and environment: what must be present for it to run.
5. Data access: models, migrations, queries, client setup.
6. Boundary shapes: route handlers, request and response models, published event or message types.
7. Infra and deploy files: Dockerfile, compose, CI, systemd, Terraform.

Open a module when a section needs what is inside it, such as a retry policy or a response shape. Do not open one to catalogue its classes, and do not read every file.

**Report, do not document, a contradiction between the code and its committed config** (compose builds an image with no Dockerfile, config requires a variable nothing sets). That is a defect, not architecture. Tell the user and keep it out of the file.

## Component or external dependency

One question settles which section a thing belongs to: **do you deploy it?**

- Deployed as part of this system, including the Postgres or Redis in your own compose file: it is a component, and a store you deploy also gets a row in data stores.
- Called but not deployed by you, a third-party API or a managed service someone else runs: it is an external dependency.

A store must not appear as both a data store and an external dependency.

## Keeping the sections apart

| Section | Answers | Not this |
|---|---|---|
| Constraints that shape this | Limits from outside the code that the shape has to live inside | A limit this shape imposes, which is the last section |
| System context | Who is outside the system and what it exchanges with them | The inside of the system |
| Components | Static ownership: which unit owns what | A trace of a request |
| Data flow | One runtime path, in order, end to end | A second listing of the components |
| Interfaces and contracts | The shapes at *your* boundary that others depend on | Shapes owned by someone else |
| External dependencies | What you call but do not deploy, and what its outage does to you | Anything you deploy yourself |
| Data stores | What holds what, and which is the source of truth | A schema |
| Scale and reliability | The mechanism, and what *your own* processes do on failure | A dependency's outage, or a target |
| Open questions | Something unresolved that would change a component or an edge | A question whose answer changes nothing |
| Limits and non-goals | What this shape cannot do, and what it deliberately will not do | A schedule for removing the limit |

## What belongs elsewhere

- **History.** No "we used to", no changelog, no migration notes. Current shape only.
- **A schedule.** Planned marks intended structure, not a roadmap. "A worker process owns the queue" is shape whether or not it exists yet. "Add the worker in Q3" is a plan and belongs in a PRD or a spec.
- **Requirements.** What the system *must* do, its acceptance and success criteria, belong to the PRD. This file says what it *does*.
- **Product intent.** Goals, scope, and product non-goals belong to `docs/vision.md`.
- **Why a decision was made.** That belongs to an ADR in `docs/adr/`. Link the ADR inline on the line it explains; never summarize it here and never add an ADR list.
- **Per-class detail.** Components are runnable or deployable units, not classes, functions, or files.

A missing mechanism is a property of the shape, not a gap to hide. "Nothing authenticates the HTTP surface" is architecture and belongs in the file. "We should add auth" does not.
