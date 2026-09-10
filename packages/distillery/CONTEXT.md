# Distillery

A personal service that watches a person's digital sources, filters what shows up against topics they've defined, and delivers a digest they can act on (create a calendar event, create a task) without having to read the sources themselves.

## Language

**Topic**:
A named area of interest the user wants tracked, defined by a Focus and backed by one or more Sources. A Topic cannot exist without at least one connected Source.
_Avoid_: Interest, category, feed

**Focus**:
The free-text statement of what the user is searching for within a Topic, written when the Topic is created. Refined over time by Feedback.
_Avoid_: Description, prompt, query

**Source**:
A connected external channel (e.g. a Telegram chat, a Telegram channel, an Instagram account) that Distillery reads from. One Source can feed multiple Topics; one Topic can draw from multiple Sources.
_Avoid_: Feed, channel (ambiguous with Telegram's own "channel")

**Finding**:
A single piece of content pulled from a Source and judged by the LLM against a Topic's Focus. The unit of discovery.
_Avoid_: Item, result, hit

**Digest**:
The delivered message for a Topic's run, made up of Blocks. Delivered on the Topic's schedule, or produced on demand.
_Avoid_: Summary (too generic), report

**Block**:
A single Finding's presentation inside a Digest: a brief tying the Finding to the Topic's Focus, a relevance label, and a link back to the original Source content.
_Avoid_: Card, entry

**Feedback**:
The user's explicit, freely-written reaction to a Finding, given after receiving a Digest. Analyzed by the LLM and merged into the Topic's Focus (partially, fully, or as an addition), teaching Distillery the user's preferences over time. Distillery never infers Feedback; the user must state it. After merging, Distillery informs the user of the new Focus text — this is informational, not a gate; the user can send further Feedback if the update missed the mark.
_Avoid_: Rating, review

**Action Request**:
The user's explicit instruction, given in reply to a Digest or Block, to create a calendar event or task, including its details. Distillery never proposes actions on its own; it only ever reacts to an Action Request.
_Avoid_: Suggestion, recommendation (Distillery doesn't make these)
