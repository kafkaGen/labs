# One always-on process, not scheduled invocations

Telegram invalidates a user session the moment it sees the same auth key on two connections (`AUTH_KEY_DUPLICATED`, 406), and recovering means an interactive SMS login on a headless host, so exactly one process may ever hold Distillery's user session. Distillery therefore runs as a single always-on async process — bot, scheduler, and Runs on one event loop — on one small VM, rather than as scheduled serverless invocations.

## Considered options

- Lambda plus a scheduler — rejected on three counts: the MTProto session has nowhere durable to live (a SQLite session file on EFS invites lock corruption, a string session in object storage races between invocations and risks invalidating the auth key), the 15-minute execution ceiling cannot hold a long-poll, and pinning egress to one address needs a NAT Gateway at roughly $33/month, about five times the cost of the whole VM.
- Two processes, an interactive bot and a separate Run worker — rejected: any overlap on the user session invalidates it.
- Managed containers (App Runner, DigitalOcean App Platform) — rejected: no persistent volume for the session file, and request-driven CPU freezing breaks both the long-poll and the scheduler.
- One always-on process on one small VM — chosen.

## Consequences

- The process is a single point of failure with no redundancy. Accepted: high availability is an explicit non-goal.
- Deploying is a restart, and a restart must fully release the Telegram session before the replacement process claims it.
- Growth is vertical only. More Topics means a longer Run, never more workers.
