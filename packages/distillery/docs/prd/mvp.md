# PRD: Distillery MVP

**Status:** Draft
**One-line pitch:** A personal Telegram bot that watches your Telegram and Instagram Sources, judges what's happening against Topics you define, and delivers a Digest you can react to — give Feedback to sharpen it, or an Action Request to turn a Block into a calendar event or task.

## 1. Problem

You have more sources of information (Telegram chats/channels, Instagram pages) than you can read. You either leave them unread for a long time or keep them around and miss the opportunities buried in them — you don't want to scroll and manually verify every post, paper, or idea just to catch the few that matter.

Today the only workaround is scrolling each Source yourself, which is exactly the cost that's driving the problem. Nothing else exists that reads sources *for* you against a definition of what you personally care about, then hands you back only the findings and a way to act on them.

You're well placed to build this: you're the only user, you already know exactly which sources and topics matter to you, and there's no need to generalize the product beyond your own workflow yet.

Why now: the source list keeps growing past what's manually reviewable, and an LLM is now capable of judging a piece of content against a free-text Focus well enough to make this worth automating.

## 2. Solution

Distillery is a personal Telegram bot that sits between you and your Sources. You define Topics — each with a Focus (what you're looking for), a Window (how far back to look), and a Schedule (how often) — and attach Telegram/Instagram Sources to them. On Schedule or on demand, it reads those Sources, judges every piece of content against the Topic's Focus with an LLM, and sends you one Digest with the result already sorted into Full Match / Partial Match / Off Topic Blocks.

This solves the problem directly: the cost driving the problem is *your* time spent scrolling and judging relevance yourself, and the LLM step is exactly what removes that cost — it does the reading and the relevance judgment, so you only ever see the few things worth seeing. The Feedback loop closes the gap a one-shot filter would leave open: a static keyword filter or RSS reader can't learn what "interesting" means to you, but folding your Feedback back into the Focus means the filter gets sharper the more you use it. The Action Request step is what makes a Digest actionable rather than just another feed to read: turning a Block straight into a Calendar event or Task is what actually stops an opportunity from being missed, which is the failure mode this exists to prevent.

Why this over the alternatives: a generic RSS/read-later tool (Feedly, Pocket) has no notion of your personal Focus or Match Level, and none of them can act on a calendar or task list — you'd still be the one doing the judging and the acting. Building your own filter rules (keyword lists, regex) would be cheaper to build but can't handle free-text nuance or improve from Feedback the way an LLM judgment can.

## 3. Target users

Single user: you. This is an internal, personal tool for v1 — no other users, no discovery problem, no onboarding beyond your own setup.

**Scenario 1 — set up a Topic and get a Digest.**
You create a Topic ("AI Grants") via a bot command, set its Focus ("grants and funding calls for small AI research teams, especially with near-term deadlines"), its Window (last 2 weeks), and its Schedule (every 2 weeks). You attach a few Telegram channels and an Instagram account as Sources. On Schedule (or on demand), Distillery runs: it pulls content from those Sources within the Window, judges each piece against the Focus, and sends you one Digest message with numbered Blocks — a brief, a Match Level, and a link — capped at 1–2 Off Topic Blocks.

**Scenario 2 — give Feedback.**
Block 4 in that Digest was a Partial Match, but it's not actually what you want. You reply to the Digest: "block 4 was too broad, I only care about grants with a deadline in the next month." Distillery's LLM folds that into the Topic's Focus and replies with the updated Focus text. You don't approve it — you just see it, and can send more Feedback if it's still off.

**Scenario 3 — act on a Block.**
Block 2 is a real opportunity. You reply to the Digest: "block 2, put this on my calendar next Thursday at 10am." Distillery parses the reply, creates the Google Calendar event immediately, and confirms it back to you — no preview, no approval step.

## 4. Definition of done

Over a few weeks of real use, you stop manually scrolling your Telegram/Instagram Sources for opportunities and instead act only on what Distillery's Digests surface.

Measured informally, since this is a single-user MVP: you notice the drop in direct scrolling, and you can point to at least one Feedback or Action Request taken from a Digest most weeks. No analytics instrumentation planned for v1.

## 5. Scope

**In for v1:**
- Topics: create / edit (Focus, Window, Schedule) / delete, via Telegram bot slash-commands.
- Sources: Telegram chats and channels (read via a personal-account session, not just a bot) and Instagram accounts (read via scraping). One Source can feed multiple Topics; one Topic can draw from multiple Sources.
- Schedule presets per Topic: daily, weekly, every 2 weeks, monthly, or on-demand only.
- Runs: fire automatically per Schedule or triggered on demand from the bot. Each Run re-scans the full Window fresh — no memory of Findings a previous Run already showed.
- Digest: one bot message per Run with numbered Blocks (brief, Match Level, source link). Match Level is Full Match, Partial Match, or Off Topic; at most 1–2 Off Topic Blocks per Digest.
- Feedback: free-text reply to a Digest, naming one or more Blocks; the LLM merges it into the Topic's Focus and reports the updated Focus back. Never a gate — you can send more Feedback anytime.
- Action Request: free-text reply to a Digest, naming one or more Blocks; creates a Google Calendar event or a Google Tasks task immediately, no confirmation step.
- Single Telegram account (personal session + bot) and single Google account — no auth, no multi-tenancy.

**Out of scope for now (and why):**
- Twitter/X, Meta Threads, Reddit, newspaper sites, WhatsApp as Sources — fast-followers once Telegram + Instagram prove the loop; each is a new connector, not a redesign.
- Multi-user, auth, permissions — MVP is single-user by design; retrofitting this later is a real redesign, not an add-on, so it's deliberately not built now.
- A confirmation/preview step before an Action Request executes — deferred; add it later only if immediate execution proves error-prone in practice.
- Deduplicating Findings across Runs of the same Topic — deferred; accepted risk of repeat Blocks, traded for v1 simplicity.
- Any interface beyond the Telegram bot (web dashboard, mobile app) — unnecessary for a single user.

## 6. Features

- [must] **Topic management** — create / edit / delete a Topic (Focus, Window, Schedule) via bot slash-commands. Addresses: too many sources with no place to define what you actually care about.
- [must] **Source attachment** — attach Telegram chats/channels and Instagram accounts to one or more Topics. Addresses: the multi-source overload itself.
- [must] **Run engine** — scheduled and on-demand triggers; applies a Topic's Window; produces Findings by judging Source content against the Focus.
- [must] **Digest delivery** — one Telegram message per Run: numbered, Match-Level-labeled, linked Blocks, Off Topic capped at 1–2. Addresses: not wanting to scroll every source yourself.
- [must] **Feedback loop** — reply-to-Digest free text, LLM-merged into the Focus, updated Focus reported back. Addresses: the tool should get better at knowing what you want over time.
- [must] **Action Requests** — reply-to-Digest free text creates a Google Calendar event or Google Tasks task immediately. Addresses: seeing an opportunity but not acting on it.
- [nice] **Digest/Finding history** — retained and queryable, so you can look back at what a Topic has surfaced over time.

## 7. Minimum acceptable criteria

Skipped — single-user personal tool. No external SLA, no support channel beyond you.

## 8. Assumptions & risks

- **Users:** you're the only user for all of v1; no auth, roles, or multi-tenancy needed.
- **Technology:**
  - Reading Telegram Sources through a personal-account session (not just a bot) risks Telegram flagging or limiting that account — accepted for v1 (ADR candidate, see below).
  - Instagram has no official API for reading followed accounts; scraping risks the Instagram account being flagged or banned — accepted for v1 (ADR candidate, see below).
  - LLM judgment against a free-text Focus is unproven; a vague Focus will likely produce noisy Match Levels until a few Feedback rounds tighten it.
  - No dedup means the same Finding can resurface across multiple Runs of a Topic within its Window — accepted for v1 simplicity.
- **Business model:** none — personal tool, not monetized.
- **What could kill this:** if the LLM's relevance judgment is unreliable enough that Full Match Blocks are frequently wrong, you'll stop trusting Digests and go back to manual scrolling — the exact failure mode this is meant to prevent. Cheap check: run it on one real Topic for two weeks before adding more Topics or Sources.

## 9. Open questions

- Exact UX for identifying a new Source (forwarding a message vs. pasting a handle/link) — implementation detail, resolved during build, not a product-level decision.
- Where and how long Digest/Finding history is retained — implementation design, not blocking v1 scope.
- Which LLM provider and prompt design judges Findings against a Focus — implementation detail.
