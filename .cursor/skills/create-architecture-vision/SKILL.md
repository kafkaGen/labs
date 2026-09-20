---
name: create-architecture-vision
description: Guide the user through writing a technical architecture vision document for a new or existing project - system context, components, tech stack, hosting, non-functional priorities, and the trade-offs behind each - through batched questions, Mermaid C4 diagrams, and ADRs, then draft the doc from a template. Use when the user asks to write, draft, or plan a technical architecture, architecture vision, system design doc, or asks "how should this be built" after the PRD is settled.
disable-model-invocation: true
---

# Create architecture vision

## What an architecture vision doc is

It's the one-time, system-level record of what exists, how it fits together, and why. It sits between the PRD (the problem and the why — see `/create-prd`, not repeated here) and per-feature specs (the how, in detail — also out of scope here). Don't re-litigate the PRD's problem/users/success-metric; pull them forward as settled inputs. Don't descend into one feature's implementation; that's a later, smaller doc.

Keep it proportional to the system. **Non-negotiable even for a single-file script:** system context (one sentence is fine), goals/non-goals, a stated tech stack and hosting answer, the top 2-3 non-functional priorities, and success criteria. Skipping these is the same failure mode as skipping "problem" in a PRD: you can't tell later whether you built what you meant to. Everything else (Container/Component split, a formal ADR log, full quality-scenario tables, a Deployment diagram) scales up only once there's more than one component or more than one person involved.

## Process

1. **Orient.** Find this project's PRD (`packages/<project>/docs/prd/*.md` or `docs/prd/*.md`) and read it: its problem, users, success metric, and scope are inputs here, not decisions to reopen. Read that project's `CONTEXT.md` if it exists, so this doc uses the glossary's terms. Gauge the system's size now (one script, one service, several services): that gauge decides which template sections in step 3 earn their place.

2. **Grill.** Follow `/grilling`. The design tree, in dependency order:

   - System context and scope: who/what does this talk to? What's the breadth and time horizon of this architecture effort?
   - Goals and non-goals: what is this trying to achieve, and what plausible goal is deliberately *not* one (scale, compliance, multi-region)?
   - Quality priorities as concrete scenarios: for each top-3-5 non-functional priority, what's the actual stimulus → response → measure, not a buzzword like "fast"? If there's no real load yet, say so and write an explicit, revisitable assumption rather than skip it or invent false precision.
   - Architectural drivers: of everything gathered so far, which 2-5 things will actually shape the structure?
   - Components and responsibilities: what are the deployable/runnable units, and what does each own? (A single script has one component; don't force a split it doesn't need.)
   - Communication and interfaces between components: sync/async, protocol, data shape (sketch, not a full schema) — skip entirely for one component.
   - Tech stack and hosting, with rationale once there's a real alternative to justify.
   - Alternatives considered and rejected: for each major choice, what else was on the table and why did it lose? Generate at least two real candidates before picking, don't rationalize a single option after the fact.
   - Risks and unknowns (technical only; product-market risk is the PRD's job).
   - Success criteria for the architecture itself: how will you know the *architecture* held up, not just the product?

   Don't push for validated load numbers or infra the user hasn't already decided on: fall back to a stated assumption and move on, same as `/grilling`'s general rule.

   When a question needs a fact neither of you has (a library's actual guarantees, a cloud service's pricing model, a framework's constraint), dispatch a background subagent (`/research`, or a `Task` call) rather than asking the user to look it up.

   **Name things as you go.** Follow `/domain-modeling` whenever a round names a domain concept, a component, or a boundary that isn't already in the glossary. Capture it in the owning context's `CONTEXT.md` immediately, not at draft time.

   **Spin off ADRs as decisions land**, not after the draft is done. A tech-stack pick, a monolith-vs-services call, a hosting choice, or a rejected alternative worth remembering each qualify under `/domain-modeling`'s ADR-FORMAT rule (hard to reverse, surprising without context, a real trade-off) the moment they're settled in this round, not when you get to the "Architecture decisions" section of the template.

3. **Diagram.** Sketch diagrams as soon as the round that produces their inputs closes, before writing prose:

   - **System Context** — as soon as scope (round 1) is settled. Non-negotiable, even if it's a one-box, one-sentence diagram for a trivial system.
   - **Container** — as soon as components and their communication (rounds 5-6) are settled. Skip only for a genuine single-component system.
   - **Deployment** — only if hosting (round 7) involves more than "runs locally" or a single managed service.

   Use Mermaid's C4 diagram types (`C4Context`, `C4Container`, `C4Deployment`). See [`MERMAID-DIAGRAMS.md`](MERMAID-DIAGRAMS.md) for syntax and a worked example of each. Render inline in the draft, not as a separate file.

4. **Draft** the doc using [`ARCHITECTURE-TEMPLATE.md`](ARCHITECTURE-TEMPLATE.md), filled from the grill answers and diagrams. Use the glossary's canonical term for every domain concept, never a synonym listed under `_Avoid_`. Drop any section that doesn't earn its place for this system's size (per the "always required?" column in the template) and say out loud which ones and why.

5. **Review together.** Walk through the draft section by section. Flag weak spots yourself: a context diagram with no external actors, a goal with no matching non-goal, a component with no stated responsibility, a quality priority with no measurable scenario. Revise from feedback. A term the draft leans on that never made it into `CONTEXT.md`, or a decision that never became an ADR, is a weak spot: follow `/domain-modeling` and settle it before moving on.

6. **Save.**

   - About an existing project under `packages/`: save to `packages/<project>/docs/architecture/vision.md`. Create `docs/architecture/` under that package if it's missing.
   - Otherwise save to `docs/architecture/vision.md` at the repo root: repo-wide architecture, or a new project with no package of its own yet.

   Say the path you used. If more than one package could fit, pick the one the doc actually describes; if that's still unclear, ask.
