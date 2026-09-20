# Distillery

A personal service that watches a user's digital Sources, filters what shows up against Topics they've defined, and delivers a Digest they can react to: giving Feedback that refines the Topic, or an Action Request that creates a calendar event or task.

## Language

**Topic**:
A named area of interest the user tracks, defined by a Focus, a Window, and a Schedule, and backed by one or more Sources. A Topic cannot exist without at least one connected Source.
_Avoid_: Interest, category, feed

**Focus**:
The free-text statement of what the user is looking for within a Topic. Set when the Topic is created, refined over time by Feedback.
_Avoid_: Description, prompt, query

**Source**:
A connected external channel (a Telegram chat, a Telegram channel, or an Instagram account) that Distillery reads from. One Source can feed multiple Topics; one Topic can draw from multiple Sources.
_Avoid_: Feed, channel (ambiguous with Telegram's own "channel")

**Connector**:
The per-platform reader that supplies a Run with content from one Source. There is one Connector per kind of platform; supporting a new kind of Source means adding a Connector, not changing how Runs work.
_Avoid_: Adapter, integration, scraper, provider

**Window**:
The fixed lookback period configured on a Topic (e.g. the last 2 weeks) that bounds which Source content a Run considers. Every Run re-applies the same Window from "now," regardless of when the Topic last ran; a Run does not skip content just because a previous Run already showed it.
_Avoid_: Lookback, range, period

**Schedule**:
How often a Topic's Run fires automatically: one of a fixed set of presets (daily, weekly, every 2 weeks, monthly) or on-demand only. A Topic set to on-demand only never fires by itself; the user triggers each Run from the bot.
_Avoid_: Cron, interval, frequency

**Run**:
One execution of a Topic's analysis over its Window, producing a Digest. Fired by the Topic's Schedule or triggered on demand.
_Avoid_: Job, execution, cycle

**Finding**:
A single piece of content pulled from a Source during a Run, and the unit the LLM judges against the Topic's Focus.
_Avoid_: Item, result, hit

**Digest**:
Everything the bot delivers at the end of a Run, made up of Blocks. One message where its Blocks fit, split across several where they don't.
_Avoid_: Summary (too generic), report

**Block**:
One Finding's entry inside a Digest: a numbered brief tying the Finding to the Topic's Focus, a Match Level, and a link back to the original Source content.
_Avoid_: Card, entry

**Match Level**:
The one of three labels the LLM assigns a Block: Full Match (squarely inside the Focus), Partial Match (adjacent to it), or Off Topic (deliberately outside it, kept rare, to surface things worth seeing anyway). A Digest caps Off Topic Blocks at 1–2.
_Avoid_: Label, tag, score

**Feedback**:
The user's free-text reaction to one or more Blocks, sent as a reply to a Digest. The LLM merges it into the Topic's Focus and reports back the updated Focus. This is informational, not a gate: Distillery never waits for approval, and the user can send further Feedback if the update missed the mark. Distillery never infers Feedback; the user must state it.
_Avoid_: Rating, review

**Action Request**:
The user's free-text instruction, sent as a reply to a Digest, naming one or more Blocks and asking Distillery to create a Google Calendar event or a Google Tasks task from them. The LLM parses the target Block(s) and the action's details, then executes immediately, with no confirmation step. Distillery never proposes actions on its own; it only ever reacts to an Action Request.
_Avoid_: Suggestion, recommendation (Distillery doesn't make these)
