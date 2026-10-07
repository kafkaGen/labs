"""Build the log envelope and wire structlog processors for both event kinds."""

from __future__ import annotations

from collections.abc import Callable

import structlog
from structlog.typing import EventDict, ExcInfo

from labs_logging.normalize import normalize

__all__ = [
    "EnvelopeBuilder",
    "foreign_pre_chain",
    "format_exception",
    "producer_processors",
    "renderer_for",
]

# Record attributes that the producer-side filter writes for the foreign chain.
CAPTURED_ATTRS = ("labs_context", "labs_runtime", "labs_ts", "labs_exception")

_ENVELOPE_KEYS = (
    "timestamp",
    "level",
    "logger",
    "application",
    "run_id",
    "process_id",
    "event",
    "exception",
)


class EnvelopeBuilder:
    """Partition an event dict into ordered envelope fields and a nested context."""

    def __init__(self, *, application: str, run_id: str, process_id: str) -> None:
        self._meta = {"application": application, "run_id": run_id, "process_id": process_id}

    def build(
        self, logger: object | None, method_name: str | None, event_dict: EventDict
    ) -> EventDict:
        captured = event_dict.pop("_captured_context", {})
        # Runtime fields come from the builder, or from a foreign record's captured
        # runtime; a caller field with the same name goes to `context`.
        runtime = {**self._meta, **event_dict.pop("_runtime", {})}
        context: dict[str, object] = {}
        for key in self._meta:
            if key in event_dict:
                context[key] = event_dict.pop(key)
        event_dict.update(runtime)
        for key in list(event_dict):
            if key in _ENVELOPE_KEYS or key.startswith("_"):
                continue
            context[key] = event_dict.pop(key)
        context = {**captured, **context}

        ordered: dict[str, object] = {
            key: event_dict[key] for key in _ENVELOPE_KEYS if key in event_dict
        }
        ordered["context"] = context
        return ordered


def _add_logger_name(_, __, event_dict: EventDict) -> EventDict:
    record = event_dict.get("_record")
    event_dict["logger"] = record.name if record is not None else "root"
    return event_dict


def _add_log_level(_, method_name: str | None, event_dict: EventDict) -> EventDict:
    # `foreign_pre_chain` runs against a parsed record when driven directly, so
    # the level must come from the record, not the processor's `method_name`.
    record = event_dict.get("_record")
    event_dict["level"] = (
        record.levelname.lower() if record is not None else (method_name or "info")
    )
    return event_dict


def _inject_captured(_, __, event_dict: EventDict) -> EventDict:
    record = event_dict.get("_record")
    if record is not None:
        event_dict["timestamp"] = getattr(record, "labs_ts", None)
        names = ("application", "run_id", "process_id")
        values = getattr(record, "labs_runtime", (None, None, None))
        event_dict["_runtime"] = {
            name: value for name, value in zip(names, values, strict=True) if value is not None
        }
        event_dict["_captured_context"] = getattr(record, "labs_context", {})
        # `ExtraAdder` copied the transport attributes into the event dict;
        # they are runtime metadata, not context, so drop them before `build`.
        for key in CAPTURED_ATTRS:
            event_dict.pop(key, None)
    return event_dict


def format_exception(exc_info: ExcInfo) -> str:
    """Render an exception as one traceback string, without frame locals."""
    return structlog.processors.format_exc_info(None, "", {"exc_info": exc_info})["exception"]


def _format_foreign_exception(_, __, event_dict: EventDict) -> EventDict:
    # `ProcessorFormatter` copies `exc_info` and `stack_info` into the event dict.
    # Drop `stack_info` (no envelope field). The producer-side filter normally
    # formatted the traceback already; format here only for records it never saw.
    exc_info = event_dict.pop("exc_info", None)
    event_dict.pop("stack_info", None)
    record = event_dict.get("_record")
    captured = event_dict.pop("labs_exception", None)
    if captured is None and record is not None:
        captured = getattr(record, "labs_exception", None)
    if captured is not None:
        event_dict["exception"] = captured
        return event_dict
    if not exc_info and record is not None:
        exc_info = record.exc_info
    if exc_info:
        event_dict["exception"] = format_exception(exc_info)
    return event_dict


def _normalize_values(_, __, event_dict: EventDict) -> EventDict:
    # Snapshot every value now: the listener thread serializes it later.
    return {key: normalize(value) for key, value in event_dict.items()}


def producer_processors(builder: EnvelopeBuilder) -> list[Callable]:
    """Structlog processors that run in the producing thread or task."""
    return [
        structlog.contextvars.merge_contextvars,
        structlog.stdlib.add_log_level,
        structlog.stdlib.add_logger_name,
        structlog.stdlib.PositionalArgumentsFormatter(),
        structlog.processors.TimeStamper(fmt="iso", utc=True, key="timestamp"),
        structlog.processors.format_exc_info,
        _normalize_values,
        builder.build,
        structlog.stdlib.ProcessorFormatter.wrap_for_formatter,
    ]


def foreign_pre_chain(builder: EnvelopeBuilder) -> list[Callable]:
    """Processors for standard-library records; timestamp and context come from the filter."""
    return [
        structlog.stdlib.ExtraAdder(),
        _add_log_level,
        _add_logger_name,
        _format_foreign_exception,
        _inject_captured,
        builder.build,
    ]


def renderer_for(console_json: bool, colors: bool) -> Callable:
    """A ProcessorFormatter renderer: console or JSON."""
    if console_json:
        return structlog.processors.JSONRenderer(sort_keys=True, ensure_ascii=False)
    # The exception is already a string; the default rich formatter would warn about it.
    return structlog.dev.ConsoleRenderer(
        colors=colors, exception_formatter=structlog.dev.plain_traceback
    )
