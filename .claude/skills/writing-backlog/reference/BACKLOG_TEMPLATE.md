<!--
One area, one file: docs/backlog/<area>.md.
Status and dependencies live only in the Index. Feature sections never repeat them.
Every feature: one to three sentences of behaviour, requirement lines for product choices only, one or two "Done when" checks.
No acceptance criteria, no mechanism, no research: each feature's spec does that when it is picked.
F1 is the walking skeleton: the thinnest path that works end to end.
IDs are never reused. Done and dropped features stay.
Delete Rules or Open decisions when they have no entries.
-->

# Backlog: <area name>

**Serves:** <the goal or in-scope line from [`../vision.md`](../vision.md) this area takes on>
**In one line:** <what this area does once every feature is built>

## Rules

Product rules every feature in this area keeps.

- ...

## Index

| ID | Feature | Status | Depends on | Change |
|----|---------|--------|------------|--------|
| F1 | <walking skeleton, five words or fewer> | todo | | |
| F2 | ... | todo | F1 | |
| F3 | ... | todo | F1, D1 | |

## Open decisions

- **D1** <product or scope question>. Blocks F3.

## Features

### F1 <name>

<One to three sentences: what works once this is built, as behaviour someone sees.>

- <requirement: a product choice, a default, a limit>
- Open: <a how-question for this feature's spec>

**Done when:** <one or two observable checks>

### F2 <name>

...

**Done when:** ...

<!-- Revising a done feature: a new ID whose first line is "Revises F1." -->
<!-- Dropped: keep the section, replace the body with "Dropped YYYY-MM-DD: <reason>." or "Split into F7, F8." -->
