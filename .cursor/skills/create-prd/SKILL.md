---
name: create-prd
description: Guide the user through writing a Product Requirements Document (PRD) for a new project or feature: clarify the problem, users, and scope through batched questions, delegate open unknowns to background research, then draft the doc from a template. Use when the user asks to write, draft, plan, or scope a PRD, product requirements doc, or a new idea that needs the problem and scope nailed down before building.
---

# Create PRD

## What a PRD is

A PRD answers three questions before anyone writes code: what problem this solves, who it's for, and what "done" looks like. It's the source of truth so everyone touching the project, including future you, stays aligned on *what* to build, not *how*. Writing it forces the fog out of an idea early, before it costs real time: skip straight to a feature list and you usually end up building the wrong thing well.

Keep it proportional to the project. A weekend script needs four sentences. Nothing produced by this skill should need more than a page or two, even for something bigger.

## Process

1. **Orient.** Use whatever's already in the conversation or codebase about the idea. Don't ask for information you can already infer.

2. **Reduce the fog in rounds.** Map the template's sections as a **design tree**: problem and why now, then target users and scenarios, then definition of done, then scope (in/out), then features, then assumptions and risks, roughly in that order since later sections lean on earlier ones. The **frontier** is every question you can ask right now without guessing at an answer that depends on something still unsettled; a question whose answer hinges on another still-open question belongs to a *later* round, not this one.

   Ask the whole frontier in one round with the `AskQuestion` tool, never one question at a time. For each question, come with your own best-guess answer and offer it as the recommended option, don't hand the user a blank field. Wait for the round's answers, then recompute the frontier: settled answers unblock the next batch of questions, and you ask that round next. Keep going until the frontier is empty.

   Don't push for real user interviews or market validation the user hasn't already done: that's out of scope for this fast, lightweight workflow. Where you'd otherwise need one, fall back to a reasonable assumption, write it into the doc as an assumption, and move on rather than blocking on validating it.

   Skip sections the project is clearly too small for. Say so instead of asking.

3. **Delegate facts, not decisions.** Finding facts is your job, never the user's. When a frontier question needs a fact neither of you already has (an unfamiliar market, a technical feasibility question, prior art), don't guess and don't ask the user to go look it up. Propose spinning up a background subagent (the `research` skill, or a `Task` call) to find it while you keep working the rest of the frontier. Only the questions that depend on that fact wait for it; ask everything else in the current round now.

4. **Draft** the PRD using [`PRD-TEMPLATE.md`](PRD-TEMPLATE.md), filled in from the answers gathered. Drop any section that doesn't earn its place for this project's size. Say out loud which sections you're dropping and why.

5. **Review together.** Walk through the draft section by section. Flag weak spots yourself (an unclear problem statement, a missing success metric) rather than waiting for the user to catch them. Revise from feedback.

6. **Save.** Match whatever convention the repo already uses for this kind of doc. If there's none, save to `docs/prd/<slug>.md` and say so.
