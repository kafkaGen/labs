# Labs

## This repo is a monorepo

Each project lives in its own directory under `packages/` and owns its code, its docs, and its decisions. The root holds only what every project shares: tooling, config, and the skills and rules in `.cursor/`.

## Docs paths are relative to a package

When a skill or an instruction names a docs path, read it as relative to the project you are working in, never to the repo root. `docs/vision.md` means `packages/<project>/docs/vision.md`. `docs/adr/` means `packages/<project>/docs/adr/`, and its numbering starts at `0001` independently of every other package. The same goes for `docs/architecture.md` and `docs/prd/`.

Before you create any file under `docs/`, name the package it belongs to. If the work spans two packages or none, ask which one owns it rather than writing to the root.
