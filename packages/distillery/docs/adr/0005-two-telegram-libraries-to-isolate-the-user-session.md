# Two Telegram libraries, to isolate the user session

Distillery runs two Telegram clients in one process: Telethon holds the personal-account MTProto session that reads Sources (see [ADR-0001](0001-personal-telegram-session-for-sources.md)), and aiogram speaks the HTTP Bot API for delivering Digests and receiving replies. Telethon can log in as a bot too, which would save a dependency, but keeping the bot half on the Bot API means it holds only a bot token and cannot reach the user auth key — the one credential whose loss costs an interactive SMS re-login on a headless host. aiogram won over python-telegram-bot because its `start_polling` is a plain coroutine that embeds in an existing event loop, where python-telegram-bot's `run_polling` blocks it and needs the lifecycle driven by hand.

## Considered options

- One Telethon client per role, both on MTProto — rejected: nothing structurally prevents bot-side code from touching the user auth key, and an MTProto bot login also forgoes the Bot API's server-side update bookkeeping.
- python-telegram-bot for the bot half — workable, but needs manual `initialize`/`start`/`stop` sequencing to share the loop.
- Telethon for the user session, aiogram for the bot — chosen.

## Consequences

- Two Telegram dependencies and two update models to hold in your head.
- Anyone later "simplifying" this to a single library removes the boundary that protects the user session. That is the reason this ADR exists.
- The bot half uses long polling. Telegram discards undelivered updates after 24 hours, so downtime beyond a day loses replies permanently.
