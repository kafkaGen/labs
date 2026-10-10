---
status: superseded by ADR-0002
date: 2026-10-04
tags: [data, structure]
---

# Isolate log files by application run

Each application launch owns a uniquely named log file, identified by its startup timestamp and a collision-resistant suffix. The user chose this over a fixed shared filename because simultaneous instances must not interfere with one another's writes or rotation. Retention counts whole runs, including their rotated backups, rather than individual files: the user explicitly wanted the newest five runs preserved even when a run has multiple backups.

## Considered options

- One fixed filename shared by independently configured processes. Rejected: concurrent processes can interfere with the same file and its rotation.
- Stable filenames per explicitly named application instance. Rejected: the user preferred automatic startup timestamps to distinguish instances.
- Unique filenames per launch with whole-run retention. Chosen.

## Consequences

- Per-file backup limits do not bound storage across launches; a separate whole-run cleanup policy is required.
- Cleanup preserves active runs, including older runs outside the newest-five window. The retained-run target is therefore not a hard storage cap while processes remain active.
- Combining independent processes into one rotating file would require a coordinated writer and is outside this design.
