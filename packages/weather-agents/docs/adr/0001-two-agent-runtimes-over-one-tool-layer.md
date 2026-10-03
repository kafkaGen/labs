---
status: accepted
date: 2026-09-22
tags: [structure, constraint]
---

# The agent layer is built twice, on the Claude API and the Claude Agent SDK, over one shared tool and prompt layer

The project exists to learn the Anthropic stack, and the Claude API and the Claude Agent SDK are two parts of that stack worth learning separately. Rather than pick one, the agent layer is implemented twice and the runtime is chosen when the CLI starts, with both implementations reading the same tools and the same prompts. The user's reason was that duplicating the same agent on the SDK is how the SDK gets learned and tested, and holding the tools and prompts fixed is what makes the two runtimes comparable at all.

## Considered options

- One runtime, the Claude API only. Rejected: it leaves the Agent SDK, which is a named part of the curriculum, untouched.
- The Agent SDK only, after the API agent works. Rejected: the user wants the two standing side by side and selectable, not one replacing the other.
- Both runtimes over one shared tool and prompt layer, selected at startup. Chosen.

## Consequences

- Tools and prompts cannot be written against either runtime's conveniences. Anything one runtime offers and the other does not has to live above the shared layer or not be used.
- Every feature lands twice, on evenings-and-weekends time. Work that only one runtime can do is a signal to revisit this record, not to quietly let the two implementations diverge.
- The success criterion that the same conversation runs correctly under both runtimes only means something while this holds.
