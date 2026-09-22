---
name: writing-adrs
description: Use when a decision with a real trade-off has just been settled and nothing records why, when the user asks to write, supersede, or deprecate an ADR or points at docs/adr/, and at the end of an architecture, grilling, or planning session that resolved architectural forks.
---

# Writing ADRs

## What an ADR is

One decision, one file, under `docs/adr/`. It records what was decided, what it was chosen over, and why, at the moment the choice was made. It is written once and never edited: to change your mind later, write a new ADR that supersedes it.

It is not a description of how the system works (`docs/architecture.md`), not intent (`docs/vision.md`), and not somewhere to work the decision out. The thinking happens first. The ADR is the receipt.

## The bar

Record a decision only when all three are true.

1. **Hard to reverse.** Changing your mind costs real time. If you could rip it out in an afternoon, it belongs in a commit message.
2. **Surprising without context.** A future reader will look at the code and wonder why on earth it was done this way.
3. **A real trade-off.** A live alternative existed and lost for a stated reason. A choice with no alternative is not a decision.

Miss one and there is nothing worth recording. Treating everything as an ADR is the same failure as a god class: a folder nobody reads because most of it is obvious.

## Never write one unprompted

**Propose, then wait for a yes.** The user decides what counts as a decision worth keeping; you only spot the candidates.

No exceptions:

- Not when the decision is obviously significant.
- Not when the user just spent an hour settling it.
- Not as a draft "for them to review" in `docs/adr/`. A file on disk is written, whatever you call it.
- Not the leftovers, after they confirmed three of your five candidates. Two rejected candidates stay unwritten.

Silence is not confirmation. Neither is the user moving on to the next topic.

## The reason has to be theirs

This is where an agent-written ADR fails. Asked to document a choice it can already see in the code or the plan, an agent invents plausible decision drivers and a plausible rejected alternative, and produces a record that reads well and is false. The rationale is the one part of an ADR that cannot be recovered from the code later, so it is also the one part where a guess does the most damage.

Every reason and every rejected option traces to something the user actually said. Where you cannot point at it, ask instead of writing. **REQUIRED SUB-SKILL:** use `grilling` when a candidate's alternative or reason is missing and the decision itself is settled.

A decision you made on your own is not an ADR. In the architecture doc it is an assumption; in code it is a commit message.

## Process

1. **Spot the candidates.** Test each against the three-part bar. Most sessions produce none, and one or two is a normal yield for a session that produced any.

2. **Propose the whole batch in one message.** One line each: what was decided, and what it beat. No drafts yet. Let the user accept them in one reply, several at a time.

3. **Draft only what they confirmed**, from [`reference/ADR_TEMPLATE.md`](reference/ADR_TEMPLATE.md), one file per decision.

4. **Save and say the paths.** List them, shortest description first, so the user can see at a glance what the session left behind.

## Numbering and naming

`docs/adr/NNNN-kebab-slug.md`. Four digits, zero padded. Read the directory, take the highest existing number, add one. Create `docs/adr/` when you write the first record and not before.

The slug is a short version of the title, lowercase with dashes: `0007-postgres-for-the-write-model.md`. Cite a record in prose as ADR-0007, and link it relatively when the reader is in another file under `docs/`.

Writing several at once: assign the numbers before drafting, so cross-references between them are right the first time.

## Frontmatter

Three fields, all required.

| Field | Value |
|---|---|
| `status` | `accepted`, `deprecated`, or `superseded by ADR-NNNN` |
| `date` | `YYYY-MM-DD`, the day the decision was made |
| `tags` | One from the list below. Two at most, and never a tag outside it. |

| Tag | Covers |
|---|---|
| `structure` | How the system splits into parts and how they talk to each other |
| `technology` | A dependency that carries lock-in: runtime, database, framework, vendor |
| `boundary` | Who owns what, what a component is not responsible for, what is deliberately not built |
| `data` | How state is stored, shaped, or retained, and which copy is the truth |
| `process` | How the project is built, tested, released, or worked on |
| `constraint` | A limit from outside the code: legal, cost, privacy, a partner's terms, a learning goal |

The tag list is closed on purpose. Freeform tags drift into synonyms and stop being useful for finding the two records that matter.

There is no `proposed` status. A record exists because the decision was made.

## Retiring a decision

**Superseded** means a later ADR replaces it. **Deprecated** means it no longer applies and nothing took its place.

Superseding touches two files:

- The new ADR carries `Supersedes [ADR-0007](0007-slug.md).` as its own line directly under the title.
- The old ADR's `status` becomes `superseded by ADR-0012`. Nothing else in it changes.

## An accepted ADR is never edited

Its context, decision, considered options, and consequences are frozen the moment it is saved. They record what was believed and why at a point in time, which is the entire reason the file exists. A record you can quietly rewrite proves nothing.

Three mechanical exceptions, and no others: the `status` field when the decision is retired, the supersession link, and a typo that changes no meaning.

Everything else is a new ADR. That includes a decision that turned out wrong, a decision whose reasoning no longer holds, and a decision that was right but has been overtaken. Write the new one, supersede the old one, and leave the old reasoning standing.

## Backfilling an old decision

A decision already in the code can get an ADR, but not by reading the code. Ask the user why it was done that way and what else was on the table, then write from their answer. Where they no longer remember the alternative, there is no ADR to write: say so and drop it.

Reconstructing rationale from a diff produces the cleanest, most confident, least true records in the folder.

## What belongs elsewhere

- How the system is put together, built or intended: `docs/architecture.md`.
- The problem, the users, the scope: `docs/vision.md`.
- A choice that was easy to make and easy to undo: the commit message.
