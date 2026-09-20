# Read Instagram Sources via scraping, accepting account-ban risk

**Status:** Superseded by [ADR-0006](0006-read-instagram-anonymously.md). The decision to read Instagram in v1 stands; the account-ban risk recorded here does not, because reading is now anonymous.

Instagram has no official API for reading content from accounts a user merely follows — only scraping (automated, unofficial access to the site) fills that gap, and it risks Instagram flagging or banning the account used to scrape. The alternative was deferring Instagram out of v1 entirely until an official or safer path exists. The user chose to accept the scraping risk for v1 instead, since Instagram Sources are part of the original problem this product exists to solve, not a later nice-to-have.

## Considered options

- Defer Instagram to a later release, ship Telegram-only for v1 — rejected: Instagram Sources are core to the problem, not optional.
- Scrape Instagram now, accept the ban/flagging risk — chosen.
