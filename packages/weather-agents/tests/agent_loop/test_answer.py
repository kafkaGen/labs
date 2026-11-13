import json

import pytest

from tests.logs import CapturedLogs
from weather_agents.agent_loop.answer import (
    ANSWER_SCHEMA,
    InvalidAnswerError,
    RunLedger,
    ToolCallSource,
    UrlSource,
    resolve_answer,
)


def model_answer(*resources: dict[str, object], answer: str = "Sunny, 21 C.") -> str:
    return json.dumps({"answer": answer, "resources": list(resources)})


def ledger_with_a_forecast_call() -> RunLedger:
    ledger = RunLedger()
    ledger.record_call("toolu_1", "open-meteo__forecast", {"latitude": 49.84, "longitude": 24.03})
    ledger.record_result('{"source": "https://open-meteo.com/en/docs", "temperature": 21}')
    return ledger


def objects_in(schema: object) -> list[dict[str, object]]:
    found: list[dict[str, object]] = []
    if isinstance(schema, dict):
        if schema.get("type") == "object":
            found.append(schema)
        for value in schema.values():
            found += objects_in(value)
    elif isinstance(schema, list):
        for value in schema:
            found += objects_in(value)
    return found


def test_every_object_in_the_schema_forbids_extra_properties():
    objects = objects_in(ANSWER_SCHEMA)
    assert len(objects) == 4
    assert all(obj.get("additionalProperties") is False for obj in objects)


def test_a_known_tool_use_id_resolves_to_the_call():
    text = model_answer(
        {"title": "Lviv forecast", "source": {"kind": "tool_call", "tool_use_id": "toolu_1"}}
    )
    answer = resolve_answer(text, ledger_with_a_forecast_call())
    assert answer.text == "Sunny, 21 C."
    assert [resource.title for resource in answer.resources] == ["Lviv forecast"]
    assert answer.resources[0].source == ToolCallSource(
        tool="open-meteo__forecast", arguments={"latitude": 49.84, "longitude": 24.03}
    )


def test_a_url_from_a_tool_result_resolves():
    text = model_answer(
        {
            "title": "Open-Meteo docs",
            "source": {"kind": "url", "url": "https://open-meteo.com/en/docs"},
        }
    )
    answer = resolve_answer(text, ledger_with_a_forecast_call())
    assert answer.resources[0].source == UrlSource(url="https://open-meteo.com/en/docs")


def test_resources_the_run_never_touched_are_dropped_and_logged(logs: CapturedLogs):
    text = model_answer(
        {"title": "Made up call", "source": {"kind": "tool_call", "tool_use_id": "toolu_9"}},
        {"title": "Made up page", "source": {"kind": "url", "url": "https://example.com/x"}},
        {"title": "Real call", "source": {"kind": "tool_call", "tool_use_id": "toolu_1"}},
    )
    answer = resolve_answer(text, ledger_with_a_forecast_call())
    assert [resource.title for resource in answer.resources] == ["Real call"]
    dropped = logs.events("answer resource dropped")
    assert [line["title"] for line in dropped] == ["Made up call", "Made up page"]
    assert all(line["level"] == "warning" for line in dropped)


def test_an_answer_with_no_resources_is_allowed():
    assert resolve_answer(model_answer(), RunLedger()).resources == []


@pytest.mark.parametrize(
    "text",
    [
        "It will be sunny.",
        json.dumps({"answer": "Sunny."}),
        json.dumps({"answer": "Sunny.", "resources": [], "mood": "happy"}),
    ],
)
def test_text_that_misses_the_schema_raises(text: str):
    with pytest.raises(InvalidAnswerError, match="did not match its schema"):
        resolve_answer(text, RunLedger())


def test_urls_lose_trailing_punctuation_and_json_escapes():
    ledger = RunLedger()
    ledger.record_result('See https://open-meteo.com/en/docs. Also "https://a.example/b?c=1",')
    assert ledger.urls == {"https://open-meteo.com/en/docs", "https://a.example/b?c=1"}
