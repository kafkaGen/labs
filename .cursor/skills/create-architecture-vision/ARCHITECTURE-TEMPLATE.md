<!--
Sections marked (always) are worth answering even for a single-file script. Sections marked
(skip if it doesn't apply) are fine to drop; say why when you drop one.
-->

# Architecture vision: <project or system name>

**Status:** Draft / Building / Shipped
**Inputs:** <one line pointing at the PRD this builds on, e.g. "Builds on `docs/prd/mvp.md`">

## 1. System context (always)

- Who and what does this talk to: users, other systems, external APIs?
- One Mermaid `C4Context` diagram. For a trivial system, one sentence is enough instead.

```mermaid
C4Context
    title System context: <name>
```

## 2. Goals and non-goals (always)

**Goals:**
- ...

**Non-goals (plausible but deliberately out):**
- ...

## 3. Components and responsibilities (always; depth scales with system size)

- What are the deployable/runnable units? For a single script, this is just "the script": say so and move on.
- One Mermaid `C4Container` diagram, plus a black-box table for anything with more than one component.

```mermaid
C4Container
    title Containers: <name>
```

| Component | Responsibility | Interfaces |
|---|---|---|
| ... | ... | ... |

## 4. Communication and interfaces (skip for a single-component system)

- How do components talk: sync/async, protocol, data format?
- Sketch of any exposed API's shape (not a full schema).

## 5. Tech stack and rationale (always state; rationale only where there's a real alternative)

| Component | Stack | Why (see ADR if non-trivial) |
|---|---|---|
| ... | ... | ... |

## 6. Hosting, deployment, and infra (always state; depth scales with system size)

- Where does this run? What cloud/infra services does it depend on, and why?
- Mermaid `C4Deployment` diagram if this is more than "runs locally" or a single managed service.

```mermaid
C4Deployment
    title Deployment: <name>
```

## 7. Functional requirements at the system level (lightweight always)

- What must the system as a whole do, stated at the system level, not per-feature?

## 8. Non-functional requirements (always name the top 2-5; full scenarios only where the stakes are real)

| Quality | Scenario (stimulus → response → measure) | Assumption? |
|---|---|---|
| ... | ... | ... |

## 9. Success criteria for the architecture (always)

- How will you know the architecture itself held up, not just the product: under what load, change, or failure was it designed to survive?

## 10. Risks and unknowns (always, keep it short)

- What's technically uncertain or risky here? (Not product-market risk — that's the PRD's job.)

## 11. Alternatives considered and rejected (skip only if there was never a real second option)

- For each major decision: what else was on the table, and specifically why did it lose?

## 12. Architecture decisions (ADR log) (skip as a separate section once ADRs already exist as files; link them instead)

- Link each ADR filed during the grill, rather than repeating its content here.
- `docs/adr/000N-slug.md` (or `packages/<project>/docs/adr/000N-slug.md`): one-line summary of the decision.
