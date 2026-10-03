---
status: accepted
date: 2026-09-22
tags: [technology, data]
---

# Open-Meteo is the single data domain, committed to rather than abstracted behind a provider interface

The MCP server needs a real data source with enough shape to justify tools, resources, and prompts, and the choice sets what every tool in the project looks like. Open-Meteo is it: the user picked it for being open and rich, with several distinct entities (forecast, archive, air quality, geocoding, marine) behind one keyless free tier. The project commits to it rather than treating the provider as swappable, since weather is the fuel for learning the Anthropic stack and a provider abstraction would be work that teaches nothing about that stack.

## Considered options

- A different weather API. Rejected: none was named that offers the same spread of entities without a key.
- Keep the provider undecided and design behind a swappable interface. Rejected: the user settled on Open-Meteo outright, and the vision already rules other data domains out of scope.
- Open-Meteo, committed to directly. Chosen.

## Consequences

- Tool, resource, and prompt boundaries follow Open-Meteo's endpoint split, so the specialist agents inherit that split too.
- The free tier's terms come with the choice: CC-BY attribution, non-commercial use, and published rate limits. If a learning experiment ever needs volume beyond them, this decision is what has to be revisited.
