# CONTEXT.md Format

## Structure

```md
# {Context Name}

{One or two sentence description of what this context is and why it exists.}

## Language

**Order**:
{A one or two sentence description of the term}
_Avoid_: Purchase, transaction

**Invoice**:
A request for payment sent to a customer after delivery.
_Avoid_: Bill, payment request

**Customer**:
A person or organization that places orders.
_Avoid_: Client, buyer, account
```

## Rules

- **Be opinionated.** When multiple words exist for the same concept, pick the best one and list the others under `_Avoid_`.
- **Keep definitions tight.** One or two sentences max. Define what it IS, not what it does.
- **Only include terms specific to this project's context.** General programming concepts (timeouts, error types, utility patterns) don't belong even if the project uses them extensively. Before adding a term, ask: is this a concept unique to this context, or a general programming concept? Only the former belongs.
- **Group terms under subheadings** when natural clusters emerge. If all terms belong to a single cohesive area, a flat list is fine.

## Which CONTEXT.md

One project under `packages/`, one context, one `CONTEXT.md` at `packages/<project>/CONTEXT.md`. The `packages/` directory *is* the list of contexts; there is no separate context map to maintain.

A root `CONTEXT.md` holds only vocabulary that every package shares. Most terms are not that, so most of the time the root file stays absent. Before writing a term, work out which package owns it (see the "Find the context before you write" section of [SKILL.md](./SKILL.md)); if two could, ask.

The `{Context Name}` heading is the project's name, not the repo's.
