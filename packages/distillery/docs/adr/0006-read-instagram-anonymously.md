# Read Instagram anonymously, without an Instagram account

[ADR-0002](0002-instagram-scraping-accepted-risk.md) accepted the risk of an Instagram account being banned, on the premise that scraping was the only way to read accounts the user follows. That premise was incomplete: the Graph API's `business_discovery` does return another account's media, but only when both the user's own account and the target account are Business or Creator accounts, which Distillery's Sources are not reliably. Distillery instead reads public Instagram content anonymously with instaloader, which puts no Instagram account at risk at all.

## Considered options

- `business_discovery` via an own Business account and a linked Facebook Page — rejected: returns nothing for personal target accounts, so it cannot cover the Sources that matter. Officially sanctioned, and worth revisiting if the Source list turns out to be mostly professional accounts.
- Authenticated scraping with a burner account, plus a residential proxy for when the cloud IP is challenged — rejected: the proxy alone would cost more per month than the server, and the account remains bannable.
- Anonymous public scraping with instaloader — chosen.

## Consequences

- There is no Instagram account to ban, which removes the risk ADR-0002 accepted. In its place: instaloader breaks whenever Meta rotates its GraphQL query IDs, and fixes land on a volunteer maintainer's schedule.
- A broken Instagram Connector must therefore degrade to a partial Digest naming the failure, never a failed Run.
- Anonymous access from a datacenter IP is reportedly throttled harder than authenticated access, so Instagram reads need explicit pacing and a per-Run request cap even though no account is exposed.
- Automated collection still breaches Instagram's Terms of Use, which prohibit it whether logged in or not. Accepted for a personal tool.
- Anything gated behind a login — Stories, and possibly full profile post listings — is out of reach.
