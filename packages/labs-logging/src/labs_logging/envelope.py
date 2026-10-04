"""Build the log envelope and wire structlog processors for both event kinds."""

from __future__ import annotations

from collections.abc import Callable

import structlog
from structlog.typing import EventDict

__all__ = ["EnvelopeBuilder", "foreign_pre_chain", "producer_processors", "renderer_for"]

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

    def build(self, logger: object, method_name: str, event_dict: EventDict) -> EventDict:
        captured = event_dict.pop("_captured_context", {})
        for key, value in self._meta.items():
            event_dict.setdefault(key, value)

        context: dict[str, object] = {}
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


def _add_log_level(_, __, event_dict: EventDict) -> EventDict:
    # `foreign_pre_chain` runs against a parsed record when driven directly, so
    # the level must come from the record, not the processor's `method_name`.
    record = event_dict.get("_record")
    event_dict["level"] = record.levelname.lower() if record is not None else None
    return event_dict


def _inject_captured(_, __, event_dict: EventDict) -> EventDict:
    record = event_dict.get("_record")
    if record is not None:
        event_dict["timestamp"] = getattr(record, "labs_ts", None)
        app, run, pid = getattr(record, "labs_runtime", (None, None, None))
        event_dict["application"] = app
        event_dict["run_id"] = run
        event_dict["process_id"] = pid
        event_dict["_captured_context"] = getattr(record, "labs_context", {})
        # `ExtraAdder` copied the transport attributes into the event dict;
        # they are runtime metadata, not context, so drop them before `build`.
        for key in ("labs_context", "labs_runtime", "labs_ts"):
            event_dict.pop(key, None)
    return event_dict


def _format_foreign_exception(_, __, event_dict: EventDict) -> EventDict:
    record = event_dict.get("_record")
    if record is not None and record.exc_info:
        event_dict["exception"] = structlog.processors.format_exc_info(
            None, None, {"exc_info": record.exc_info}
        )["exception"]
    return event_dict


def producer_processors(builder: EnvelopeBuilder) -> list[Callable]:
    """Structlog processors that run in the producing thread or task."""
    return [
        structlog.contextvars.merge_contextvars,
        structlog.stdlib.add_log_level,
        structlog.stdlib.add_logger_name,
        structlog.stdlib.PositionalArgumentsFormatter(),
        structlog.processors.TimeStamper(fmt="iso", utc=True, key="timestamp"),
        structlog.processors.format_exc_info,
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
    return structlog.dev.ConsoleRenderer(colors=colors)
