# Telegram's chat history is the Digest store

Distillery resolves a Feedback or Action Request by reading the Digest text that Telegram attaches to the user's reply, so no Run, Finding, or Digest is ever persisted: the only durable state is Topics, Sources, and the links between them. The alternative was storing Digests and Blocks in a database and resolving "block 4" by lookup, which the user rejected as machinery a single-user MVP doesn't need when Telegram already retains every Digest it delivered.

## Considered options

- Persist Runs, Findings, and Digests, and resolve replies by database lookup — rejected: a schema, migrations, and a retention policy for data Telegram keeps anyway.
- Resolve replies from Telegram, but also append Findings and Digests to a write-only log — rejected for v1: insurance against a problem that hasn't appeared.
- Read the replied-to Digest text as the source of truth — chosen.

## Consequences

- The PRD's `[nice]` "retained and queryable" Digest/Finding history becomes Telegram's own search, not a query Distillery answers.
- Deleting a Digest message makes its Blocks permanently unactionable; nothing can reconstruct them.
- Every Digest message must carry in its visible text everything an Action Request needs — the Topic, Block numbers, briefs, and source links — because that text is the only record.
- Telegram's 4096-character message limit therefore forces long Digests to split across several messages, and each one must repeat the Topic and stand alone, because a reply quotes exactly one message.
