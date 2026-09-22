# Labs

## This repo is a monorepo

Each project lives in its own directory under `packages/` and owns its code, its docs, and its decisions. The root holds only what every project shares: tooling, config, and the skills and rules in `.cursor/`.

## Docs paths are relative to a package

When a skill or an instruction names a docs path, read it as relative to the project you are working in, never to the repo root. `docs/vision.md` means `packages/<project>/docs/vision.md`. `docs/adr/` means `packages/<project>/docs/adr/`, and its numbering starts at `0001` independently of every other package. The same goes for `docs/architecture.md` and `docs/prd/`.

Before you create any file under `docs/`, name the package it belongs to. If the work spans two packages or none, ask which one owns it rather than writing to the root.

## Who owns which doc

The four docs are not equally yours to touch. This holds whether or not you are inside a skill that says it.

| Doc | What you may do |
|---|---|
| `docs/vision.md` | Read it. Never edit it. If the work made it wrong, say which line and stop. |
| `docs/prd/` | Read it, and keep its `Status` line honest: `Draft` to `Building` when work starts against it, `Building` to `Shipped` once every use case in it is built. Nothing else in the file is yours. |
| `docs/adr/` | Propose it and wait for the user to say yes. Only then may you add a record, supersede one, or deprecate one. An accepted ADR is frozen apart from its `status` line. |
| `docs/architecture.md` | Yours to correct. Where the doc and the code disagree about something marked Built, the code wins and the doc gets fixed. |

The vision changes only because the user asked, in a session about that doc, and so does everything in a PRD except its status. Noticing drift is not being asked.
