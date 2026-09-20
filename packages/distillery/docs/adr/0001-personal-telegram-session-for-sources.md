# Use a personal Telegram account session, not a bot, to read Sources

A Telegram bot can only see messages in chats/channels it has been explicitly added to as a member — it can't read content from the many channels and group chats the user already follows on their personal account without asking every channel owner to add the bot. Distillery instead runs a personal-account session (a "userbot") to read Sources, and keeps a separate bot identity for the chat interface (Digests, Feedback, Action Requests). This risks Telegram flagging or rate-limiting the personal account, since userbot sessions sit outside Telegram's bot API terms; the user accepted that risk for v1 because bot-only access would make most existing Sources unreachable.

## Considered options

- Bot-only, requiring the user to add the bot to every Source — rejected: defeats the point of reading channels the user is a member of but doesn't own.
- Personal-account session for reading, bot for interaction — chosen.
