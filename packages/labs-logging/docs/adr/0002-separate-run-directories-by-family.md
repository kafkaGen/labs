---
status: accepted
date: 2026-10-10
tags: [data, structure]
---

# Keep each family's runs in its own directory

Supersedes [ADR-0001](0001-isolate-log-files-by-run.md).

One application can run several parts as separate processes, such as an MCP server and an agent runner, each configured with its own family. Under ADR-0001 all of their runs landed in one directory named only by a start time and a hash, so the user could not tell which run belonged to which family without opening `main.jsonl`, and one retention count covered every family. Each run now lives under `<log_dir>/<family>/<run>/`, and retention counts runs per family. Each run is still isolated and still keeps its backups together, as ADR-0001 decided. The user chose a folder per family because it makes the family visible when browsing the logs.

## Considered options

- One shared directory for all families of an application, as in ADR-0001. Rejected: runs show only a timestamp and a hash, so the family cannot be seen without opening the file, and retention mixes families.
- The family in the run directory or file name. Raised by the user as a way to see the family. Rejected: it fixes the naming but keeps one retention count and one flat listing across families.
- A directory per family. Chosen.

## Consequences

- `retain_runs` now means the newest runs per family, so total retained runs for an application grow with its families.
- The `.coord` lock and cleanup work inside one family directory, so one family never deletes another's runs.
- Existing run directories sitting directly under `log_dir` are no longer found by cleanup. They stay on disk until removed by hand.
