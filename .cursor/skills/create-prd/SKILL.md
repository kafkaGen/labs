---
name: create-prd
description: Guide the user through writing a Product Requirements Document (PRD) for a new project or feature: clarify the problem, users, and scope through batched questions, delegate open unknowns to background research, then draft the doc from a template. Use when the user asks to write, draft, plan, or scope a PRD, product requirements doc, or a new idea that needs the problem and scope nailed down before building.
disable-model-invocation: true
---

# Create PRD

## What a PRD is

A PRD answers three questions before anyone writes code: what problem this solves, who it's for, and what "done" looks like. It's the source of truth so everyone touching the project, including future you, stays aligned on *what* to build, not *how*. Writing it forces the fog out of an idea early, before it costs real time: skip straight to a feature list and you usually end up building the wrong thing well.

Keep it proportional to the project. A weekend script needs four sentences. Nothing produced by this skill should need more than a page or two, even for something bigger.

## Process

1. **Orient.** Use whatever's already in the conversation or codebase about the idea. Don't ask for information you can already infer. Work out which project under `packages/` this PRD belongs to (or that it's repo-wide) and read that context's `CONTEXT.md` if it exists, so you write in the language the project already uses.

2. **Grill.** Follow `/grilling` to reduce the fog. The design tree is the PRD template's sections: problem and why now, then the solution and why it's the right mechanism for that problem, then target users and scenarios, then definition of done, then scope (in/out), then features, then assumptions and risks, roughly in that order since later sections lean on earlier ones.

   Don't push for real user interviews or market validation the user hasn't already done: that's out of scope for this fast, lightweight workflow. Where you'd otherwise need one, fall back to a reasonable assumption, write it into the doc as an assumption, and move on rather than blocking on validating it.

   Skip sections the project is clearly too small for. Say so instead of asking.

   When a frontier question needs a fact neither of you already has (an unfamiliar market, a technical feasibility question, prior art), propose spinning up a background subagent (`/research`, or a `Task` call). `/grilling` already forbids asking the user to look it up.

   **Name things as you go.** A PRD is where a project's vocabulary is born, so a round that settles what something *is* has also settled what to *call* it. Follow `/domain-modeling` whenever a round names a domain concept, the user's term conflicts with the glossary, or a word is doing two jobs at once. Capture the term in the owning context's `CONTEXT.md` right then, before the next round: the PRD then reads in the same language as the code. Don't defer this to the draft; by then the fuzzy term has already spread through your questions.

3. **Draft** the PRD using [`PRD-TEMPLATE.md`](PRD-TEMPLATE.md), filled in from the answers gathered. Use the glossary's canonical term for every domain concept the draft names, never a synonym it lists under `_Avoid_`. Drop any section that doesn't earn its place for this project's size. Say out loud which sections you're dropping and why.

4. **Review together.** Walk through the draft section by section. Flag weak spots yourself (an unclear problem statement, a missing success metric) rather than waiting for the user to catch them. Revise from feedback. A term the draft leans on that never made it into `CONTEXT.md` is a weak spot: follow `/domain-modeling` and settle it.

   The PRD scopes *what* to build, so it will surface decisions worth keeping (a technology with lock-in, a deliberate no). Those are ADR material, not PRD material: hand them to `/domain-modeling` rather than burying them in the doc.

5. **Save.** Put the file next to the thing it specifies: the context you settled on in step 1.

   - PRD about an existing project under `packages/`: save to `packages/<project>/docs/prd/<slug>.md`. Create `docs/prd/` under that package if it is missing.
   - Otherwise save to `docs/prd/<slug>.md` at the repo root: repo-wide work, or a new idea with no package of its own yet.

   Say the path you used. If more than one package could fit, pick the one the PRD actually specifies; if that is still unclear, use the repo-root path.
