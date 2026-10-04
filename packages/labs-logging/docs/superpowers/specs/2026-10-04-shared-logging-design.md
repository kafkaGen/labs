# Shared Python logging package

Date: 2026-10-04
Status: Approved design; written-spec review pending
Owner: `packages/labs-logging/`
Distribution: `labs-logging`
Import: `labs_logging`

## Purpose and scope

Provide application-neutral logging that other Python packages can reuse: readable colorful terminal output, structured events, rotating local files, named logger families, and configurable standard handlers. The package uses Python >=3.12 and the repo's uv workspace/tooling conventions.

The first implementation includes a small runnable demonstration application and tests. It does not migrate weather-agents or another existing application. Cloud delivery, an external collector, shared multiprocess file writing, and repo-wide Python-rule edits are separate work. No application-specific or MCP-specific logic belongs in this library.

## Settled foundation

Use standard-library `logging` for logger hierarchy, levels, handler routing, and third-party interoperability. Use `structlog` for structured events, context support, and console/JSON rendering. This foundation was selected over plain logging with a colorful formatter and over Loguru. No separate ADR was requested for this choice.

[ADR-0001](../../adr/0001-isolate-log-files-by-run.md) records unique per-run files and whole-run retention.

## Public surface and application ownership

The public surface provides:

- A typed configuration object for application identity, logger family, levels, console/file destinations, dispatch mode, queue capacity, rotation, retention, and extra handlers.
- An explicit setup function returning a runtime handle. The handle supports shutdown, context-manager cleanup, and health/status inspection.
- Named structured loggers and scoped context binding. Ordinary standard-library logger calls remain supported.

Applications call setup once at startup and close the runtime on graceful exit. They own environment/settings parsing; the logging package accepts configuration rather than inventing an environment-variable convention. Application-local setup wrappers are allowed but not required.

Importing the package or obtaining a logger must not open files, start threads, or configure application handlers. Setup is process-wide; multiple simultaneously configured runtimes in one process are unsupported. A second setup while a runtime is active raises a configuration error rather than duplicating handlers. Setup after shutdown is supported.

Configuration includes `synchronous: bool`, default false. True selects direct handler writes; false selects background dispatch. An application settings parser may interpret `1` as true, but the Python API uses a boolean, not a worker count.

## Logger families and routing

A server application may use family `mcp_server`, with children `mcp_server.tools` and `mcp_server.resources`. Children propagate to the application's destinations; they do not install their own handlers. Each event retains its full logger name. Levels can be overridden per family/child without creating separate files. Use Python module names by default; explicit family names are appropriate when module paths do not describe the application's boundary.

The application identity used for directories can differ from the logger family, for example `mcp-server` versus `mcp_server`. Identity must be a safe single path component, not an arbitrary path.

Application setup installs one dispatch handler on the root logger, routing propagating standard-library records, including third-party records, into the same destinations. The default application and destination level is INFO. Explicit per-logger overrides permit more verbose children; handler thresholds remain independently configurable. Existing non-package handlers must not be silently removed or closed. Existing root handlers cause a setup error: applications must resolve competing configuration explicitly. Loggers with their own handlers or propagation disabled remain application-owned; setup does not rewrite them, so their records may bypass the shared destinations or produce duplicate output. Restore logger levels changed by setup on shutdown. The runtime removes and closes only resources it owns. Supplied extra handlers are caller-owned: flush them on shutdown but do not close them.

Custom standard `logging.Handler` instances can be supplied, including handlers with component filters. There is no plugin registry or cloud adapter framework. Adding a handler does not promise remote durability or retry behavior.

## Event representation and context

Local files are UTF-8 JSON Lines: one complete JSON object per event, without terminal color escapes or physical multiline tracebacks. Common fields include UTC timestamp, level, logger name, application identity, run identity, event/message, process identity, and structured contextual fields. Exception information is serialized into the event, not printed as separate file lines.

Standard-library messages and `extra` fields pass through the same normalization/rendering pipeline. The JSON envelope uses `timestamp`, `level`, `logger`, `application`, `run_id`, `process_id`, `event`, optional `exception`, and `context`. Caller-supplied fields live under `context`, so they cannot overwrite envelope fields. Explicit event fields override scoped context fields with the same key. Normalize JSON-native values recursively; represent unsupported values with a type-labelled string and fall back to the type name if conversion fails. Detect cycles rather than recursing indefinitely. Do not capture exception-frame locals by default. Logging cannot automatically guarantee the removal of secrets: callers must not submit credentials, raw private payloads, or other sensitive values.

Scoped context uses task-local context variables and restores prior values on scope exit. Context is captured in the producing thread/task before dispatch, not read later by the listener thread. Context does not automatically cross independent processes or arbitrary manually created threads. Tests establish behavior for simultaneous asyncio tasks and standard-library events.

## Console behavior

Console logging is enabled by default and uses stderr. Interactive output is readable and colorful; colors are disabled when the destination is not a terminal. Console format and color behavior can be explicitly configured, including JSON output for collectors. Console output may be disabled independently of file logging, and the stream may be replaced.

File output is enabled by default. Stream-only output is supported for managed production, where infrastructure owns collection and retention. MCP applications can preserve stdout for protocol traffic or disable console output for terminal UIs through general configuration; the package has no MCP detection.

## Local layout and file ownership

Resolve an OS-appropriate per-user application log/state directory outside the checkout. Allow an explicit application-supplied directory override; do not derive it from the current working directory or assume the installed package tree is writable. The specific platform-directory dependency and lock implementation are implementation-plan decisions.

Within the application's directory, every launch creates a run directory containing a timestamped main file, any rotated backups, and run-ownership metadata/lock. Use a filesystem-safe UTC startup timestamp with microsecond precision and a collision-resistant suffix. Create run directories exclusively and retry name collisions rather than relying on timestamps alone.

Each process owns its file writer. Separate launches of the same application never share an active file. Processes must initialize their own runtime; inherited runtime state after fork is not supported. Logger children within one process share its destinations.

A process holds an OS-level ownership lock for its run until shutdown. Startup and cleanup coordinate through an application-level lock so cleanup cannot delete a run between creation and ownership acquisition. Cleanup uses nonblocking ownership-lock acquisition to distinguish inactive runs; PID reuse, file age, and graceful-completion markers alone are insufficient. Crashes release the OS-held lock. Locking must work on supported local filesystems across supported operating systems; network filesystem semantics are not promised.

## Rotation and retention

Defaults:

- Maximum active file size: 10 MiB.
- Retained backups per run: zero.
- Retained runs per application: five.

With zero backups, rollover discards the old contents and begins again in the same main file. The default preserves recent events, not a complete run history. This is deliberate custom behavior: standard `RotatingFileHandler` with `backupCount=0` does not implement discard-and-restart rollover. Positive backup counts retain that many older segments in addition to the active file.

The byte threshold is approximate. A single oversized event may exceed it; emit that event intact rather than splitting the JSON object. Repeated rollover must neither produce empty backup chains nor lose the triggering event.

Retention keeps the newest five runs overall, plus any older runs still active. Order runs by their encoded UTC startup timestamp with a deterministic run-ID tie breaker. Deleting a run deletes its main file and all backups together. Retention never counts backups as independent runs and never deletes active runs.

Cleanup occurs at setup and graceful shutdown. The current run remains protected through its final drain and cleanup; ownership is released afterward. A crashed old run is eligible on the next cleanup. If no new lifecycle event occurs after a crash, cleanup waits until the next setup/shutdown; there is no periodic janitor in this release.

The five-run target is not a hard byte quota. Active older runs, configurable backups, and oversized events can exceed it. Strict startup surfaces failures creating destinations, acquiring coordination locks, or performing required cleanup. Cleanup ignores unrelated files and refuses unsafe paths rather than following arbitrary symlinks outside the application log root.

## Background and synchronous dispatch

Background mode uses one bounded in-process queue and one listener thread. Default capacity is 10,000 events and is configurable. Snapshot context and normalize event data before enqueueing so later context changes, mutable values, or handler formatting cannot alter the queued event or leak fields between console and file rendering.

Queue insertion is nonblocking. When full, drop the new event, increment a drop counter, and issue a rate-limited stderr diagnostic outside the logging pipeline. The diagnostic includes the accumulated drop count and cannot enqueue itself recursively. The runtime exposes drop counts for inspection.

Synchronous mode sends events directly to the configured handlers in the calling thread. It preserves formatting, context, levels, rotation, retention, and error reporting, but may block the asyncio loop. Queue capacity and overflow behavior do not apply in synchronous mode.

All destinations, including extra handlers, run on the listener thread in background mode unless an explicit future extension says otherwise. Slow destinations can cause queue overflow; adding handlers does not create independent delivery queues.

## Startup, failures, and shutdown

Setup is transactional: validate configuration, initialize destinations and ownership, and start dispatch before returning. If setup fails, raise a specific error and roll back acquired resources; do not silently fall back to console-only logging. No partially installed handlers or abandoned active ownership locks may remain.

Runtime I/O errors produce a direct diagnostic, mark the runtime unhealthy, and preserve functioning destinations. A background writer cannot raise the error in the producer that already returned. Expose error status through the runtime handle; logging is not an audit durability guarantee. Custom handler failures must not terminate dispatch to unrelated healthy handlers. Diagnostics use a path independent of the failing handlers and avoid recursion.

Graceful shutdown stops accepting new events through the runtime's pipeline, drains accepted queued events, flushes handlers, performs safe retention cleanup, and releases ownership and owned resources. Shutdown is idempotent. A race between producers and shutdown must not strand accepted records or leave an enqueue path pointing at a stopped listener. Calls after shutdown are outside the configured runtime and must not access closed resources.

Handlers must finish in finite time for drain to complete; no cancellation or remote-delivery deadline framework is included. Hard termination may lose queued events. Synchronous file writes also do not imply fsync durability after power loss.

## Module responsibilities

Keep focused units for configuration validation, runtime/dispatch lifecycle, event rendering/context, and local file rotation/ownership/retention. Standard handlers form the destination extension seam. Do not mix cloud transport, application settings, or MCP protocol behavior into these units. Concrete module names and dependencies belong in the implementation plan.

## Verification

Provide a small runnable dummy application that emits parent/child events, standard-library events, structured context, and an exception. It supports both dispatch modes and configurable destinations without needing an existing application. Automated tests include:

- Family/child routing and per-logger levels without duplicate records.
- Consistent JSON for standard-library and structlog events, contextual fields, exceptions, reserved-field handling, and unsupported values.
- Interactive color control, nonterminal output, JSON console configuration, console disabling, and stream-only operation.
- Async task context isolation, scope restoration, and producer-side snapshots in background mode.
- Discarding rollover with zero backups, positive backup counts, byte threshold behavior, and oversized records.
- Whole-run cleanup for newest-five semantics, preservation of every run's backups, deterministic ordering, and unrelated-file/path safety.
- Two independent processes with separate files; coordinated concurrent startup/cleanup; active-run exclusion; crash-released ownership.
- Strict setup failures and rollback; runtime handler failures and health reporting; queue saturation/drop diagnostics; idempotent shutdown and successful graceful drain.
- Synchronous mode creating no listener thread, background mode writing outside the producer thread, and restart after shutdown.

Use uv, Ruff, ty, pytest, and the repository's pre-commit hooks. Tests use temporary directories and do not delete or populate the user's real log directory. OS-lock tests must exercise actual process behavior, not only mocks.

## Proposed convention follow-up

A separately reviewed Python-rule update should preserve standard-library compatibility and document:

- Module/family logger naming; no request IDs or other unbounded identifiers in logger names.
- One application-owned setup, no library-owned file/console handlers at import time.
- Lazy positional formatting for standard-library messages and structured keyword fields for structlog events.
- Level choices, scoped correlation fields, exception logging at the boundary that handles the failure, and avoidance of duplicate exception reports.
- No secrets or exception-local capture; explicit destination/retention ownership.

The rule is not edited by this package's design commit. Existing vision, PRD, and architecture documents in other packages remain unchanged.

## Review and next gate

This document records the approved conversational design. Review the written spec before implementation planning. No implementation code or dependency additions are authorized by this documentation step. The user separately approved minimal metadata (`pyproject.toml` with `tool.uv.package = false`) because the workspace's `packages/*` member glob requires metadata even for this design-only directory. Packaging and installation will be enabled during implementation.
