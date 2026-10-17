import json

import anthropic
from anthropic.types import Usage

from weather_agents.agent_loop.answer import Answer, ToolCallResource, UrlResource
from weather_agents.agent_loop.result import TokenUsage


def test_an_answer_with_both_kinds_of_resource_parses_from_json():
    text = json.dumps(
        {
            "answer": "Sunny, 21 °C.",
            "resources": [
                {"kind": "url", "url": "https://open-meteo.com", "title": "Open-Meteo"},
                {
                    "kind": "tool_call",
                    "tool": "open-meteo__forecast",
                    "arguments": '{"latitude": 52.52}',
                    "title": "Forecast",
                },
            ],
        }
    )
    answer = Answer.model_validate_json(text)
    assert isinstance(answer.resources[0], UrlResource)
    assert isinstance(answer.resources[1], ToolCallResource)


def test_the_strict_schema_closes_every_object():
    schema = anthropic.transform_schema(Answer)
    objects = [schema, *schema["$defs"].values()]
    assert all(item["additionalProperties"] is False for item in objects)


def test_token_usage_adds_a_reply_including_cache_counts():
    usage = TokenUsage().add(
        Usage(
            input_tokens=10,
            output_tokens=5,
            cache_read_input_tokens=3,
            cache_creation_input_tokens=2,
        )
    )
    assert usage == TokenUsage(input=10, output=5, cache_read=3, cache_write=2)
    assert usage.add(Usage(input_tokens=1, output_tokens=1)).input == 11
