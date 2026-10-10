# labs-logging

Structured logging for Python applications in the labs monorepo. It writes colorful
console output to stderr and rotating JSON Lines files, one isolated directory per run.

## Use it

Add the workspace dependency, then follow [`docs/usage.md`](docs/usage.md) for setup,
loggers, context, handlers, threads, and tests.

```toml
[project]
dependencies = ["labs-logging"]

[tool.uv.sources]
labs-logging = { workspace = true }
```

Import with `from labs_logging import ...`. `app` names the log directory and must be one
safe path component. `family` is the logger-name prefix and the folder under it for one
process. Use the top-level package name and `get_logger(__name__)`. Importing
the package or calling `get_logger` opens no files and starts no threads. `configure`
raises `AlreadyConfiguredError` while a runtime is active in the process, and
`SetupError` when setup fails, for example because the root logger already has handlers.
A failed setup leaves nothing installed. After `shutdown()` you can configure again.

## Configuration reference

| Field | Default | Meaning |
|---|---|---|
| `level`, `level_overrides` | `INFO`, `{}` | Family level and per-logger levels. |
| `log_dir` | platform user log dir for `app` | Root of the log tree. Each family gets `<log_dir>/<family>/`. |
| `console`, `console_json`, `console_colors`, `console_stream` | on, off, auto, stderr | Console destination. Colors default to on only for a terminal. |
| `file` | on | File destination. |
| `synchronous` | `False` | `True` writes in the calling thread. `False` uses one listener thread and a bounded queue. |
| `queue_size` | 10,000 | Background queue capacity. A full queue drops the new event and counts it in `Runtime.drops`. |
| `max_bytes`, `backups` | 10 MiB, 3 | Size per file and rotated backups per run. |
| `retain_runs` | 5 | Newest runs kept per family. |
| `extra_handlers` | `[]` | Your own `logging.Handler` instances. The runtime flushes them on shutdown and never closes them. |

`Runtime.healthy`, `Runtime.errors`, `Runtime.error_count`, and `Runtime.drops` report
destination failures and dropped events. A failing handler marks the runtime unhealthy
and does not stop the other handlers.

Two lifecycle limits follow from the design. A forked child inherits the parent's
active runtime and its threads do not survive the fork, so call `configure` only after
the fork, in a fresh process. The listener thread is a daemon and nothing registers an
`atexit` hook, so a process that skips `shutdown()` can lose events still in the queue.

Windows support is written but untested. The lock uses `msvcrt` there, and only the
POSIX path (`fcntl.flock`) has run in tests.

## Files

Each launch creates `<log_dir>/<family>/<UTC start time>-<suffix>/` with `main.jsonl`, any
`main.jsonl.N` backups, and a `lock` file. Two processes never share a file. With
`backups=0`, reaching `max_bytes` discards the old contents and starts the same file
again. The size limit is approximate: one oversized event is written whole.

Setup and shutdown delete whole runs beyond the newest `retain_runs`, and never delete
a run whose process still holds its lock. A crashed run becomes deletable on the next
setup or shutdown.

Each line is one JSON object. Keys are written in alphabetical order (the renderer uses
`sort_keys`), at the top level and inside `context`. Do not rely on any other order.
The envelope keys are `application`, `context`, `event`, `level`, `logger`,
`process_id`, `run_id`, and `timestamp`, plus `exception` when there is one. Fields you
pass to a logger go under `context`, and a field of the same name as an envelope key
cannot overwrite it. The timestamp is ISO 8601 UTC with microseconds and a trailing
`Z`, for example `2026-10-04T21:00:00.000123Z`.

`labs_logging.rotation.JsonFileHandler` is the file writer. Used inside a runtime, its
errors are caught and recorded in `Runtime.errors`. Used on its own, `emit` raises on a
write or format failure instead of calling `logging`'s `handleError`.

## Testing

See the Tests section of [`docs/usage.md`](docs/usage.md).

## Event values

Values passed to the logger are copied into JSON-safe data when you call it, so later
mutation cannot change a queued event. Tuples and sets become lists, and set order is
iteration order. Cycles become `"<cycle>"`. Unsupported types become a string such as
`"Decimal: Decimal('1.5')"`, or just the type name when `repr` fails. Non-finite floats
become strings. Dict keys become strings, and keys that collide after conversion
overwrite each other. The console shows these same normalized strings, not the
original objects, so a `Decimal` appears as `Decimal: Decimal('1.5')` there too.

Standard-library messages are formatted, and tracebacks rendered, in the calling thread.
Tracebacks carry no frame locals.

`Runtime.errors` keeps the first 100 destination errors plus a count of the rest.
`Runtime.error_count` has the total. Copying costs time per call, so avoid passing very
large objects as fields. Logging is not a place for secrets: nothing is redacted.

## Example

`examples/dummy_app/` is a small package that logs from two modules with
`get_logger(__name__)`, plus a standard-library record, scoped context, and an
exception. From the repository root:

```sh
cd packages/labs-logging/examples && uv run --package labs-logging python -m dummy_app --sync
```
