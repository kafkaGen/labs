<!--
The system's shape, present tense. It may run ahead of the code, so every component, flow,
store, and dependency carries Built or Planned. Never leave a line unmarked.
Each section is short: a diagram, a table, or a few bullets.
Delete a section only when the system has none of that thing. Deleting because you could not
find the answer means you have not asked or read enough.
-->

# Architecture: <system name>

**What it is:** <one line: what the system does and what shape it takes, e.g. "A single always-on Python process that reads sources on a schedule and delivers digests over Telegram.">

**Built** means the code does this today. **Planned** means it is the intended shape and does not exist yet. Where a Planned line was assumed rather than decided, its row says so.

## Constraints that shape this

The limits the shape has to live inside, before any diagram. Pull them from `docs/vision.md` where it exists. A constraint that bent a decision below belongs here, not buried in a rationale.

- **Time and effort budget:** ...
- **Learning goals:** what the project exists to teach, and therefore what it will spend effort on that a pure delivery project would not.
- **Expected size:** how many users and how much data are expected, as stated by the user. Not a throughput claim.
- **Hard limits:** platform, money, privacy, legal, and anti-requirements ("never publicly indexed").

## System context

Who uses it and what it talks to. Only things outside the boundary appear here.

```mermaid
C4Context
```

- **<external user>**: what they do with it.
- **<external system>**: what it is used for.

## Components

The runnable or deployable units and what each one owns. Edges and their protocols live on the diagram, not in the table.

```mermaid
flowchart LR
```

| Component | Owns | Tech | Status |
|---|---|---|---|
| ... | ... | ... | Built / Planned |

`Owns` is the responsibility, not the behaviour: what it is in charge of, never how it retries, caches, or fails.

Where a component's ownership holds by convention rather than being enforced, say so in its `Owns` cell. Below the table, note any coupling the edges do not show: shared code, a shared release, a shared credential.

## Data flow

The one to three paths that carry the system's real work, end to end. Not every path. Mark each flow Built or Planned under its heading.

### <flow name> — Built / Planned

```mermaid
sequenceDiagram
```

## Interfaces and contracts

The shapes at this system's own boundaries: the API it exposes, the commands it accepts, the message or event shapes it publishes. Shape and meaning, not full schemas.

| Interface | Kind | Shape | Consumer | Status |
|---|---|---|---|---|
| ... | ... | ... | ... | Built / Planned |

## Data stores

Stores this system deploys or owns. A store someone else runs belongs under external dependencies instead.

| Store | Holds | Source of truth for | Retention | Status |
|---|---|---|---|---|
| ... | ... | ... | ... | Built / Planned |

## External dependencies

What the system calls and does not deploy, and what happens to it when each is unavailable.

| Dependency | Used for | When it is down | Status |
|---|---|---|---|
| ... | ... | ... | Built / Planned |

## Deployment and runtime

Where this runs, how it starts, and what it needs present to run. Add a diagram only when it is more than one host or runtime.

```mermaid
flowchart TB
```

## Cross-cutting concerns

| Concern | How it works here | Status |
|---|---|---|
| Authentication and authorization | ... | Built / Planned |
| Configuration and secrets | ... | Built / Planned |
| Logging and observability | ... | Built / Planned |
| Error handling and retries | ... | Built / Planned |

Delete a row only when its absence says nothing. Keep it when the absence is itself a property of the boundary, and state it as the current behaviour: "None. Any caller that reaches the port gets every endpoint."

## Scale and reliability

The mechanism and where it tops out. Where nothing measures it, give the mechanism and the constant that governs it, and leave the number out.

- **Throughput:** ...
- **Failure behaviour:** what this system's own processes do on a crash, a restart, or a dependency timeout, and what is lost.
- **Recovery:** what brings it back, and whether that is manual.

## Open questions and assumptions

**Open** — unresolved, and specifically what part of the shape would change with the answer. A question that changes nothing is not worth listing.

- **<question>**: changes <which component or edge>.

**Assumed** — things chosen without the user, and what confirms or kills each. These are not decisions and they never become ADRs without the user settling them.

- **<assumption>**: settled by <what would confirm it>.

## Limits and non-goals

What this shape cannot do, and what it deliberately will not do. Link an ADR on the line it explains, when one exists.

- **<limit>**: ... (see `docs/adr/000N-slug.md`)
- **Not <architectural non-goal>**: ... and why the structure rules it out.
