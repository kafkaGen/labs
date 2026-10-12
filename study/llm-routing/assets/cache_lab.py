# /// script
# requires-python = ">=3.12"
# dependencies = ["anthropic"]
# ///
"""Cache lab: run routing moves against the Claude API and print what each does to the cache.

Run from the repo root:

    ANTHROPIC_API_KEY=... uv run --no-project study/llm-routing/assets/cache_lab.py

Every request uses max_tokens=0, so the API reads the prompt, writes the cache,
and returns usage without generating output. Expect well under $0.15 per run.
"""

import os
import sys
import uuid

import anthropic

MAIN_MODEL = "claude-sonnet-5-5"
SWITCH_MODEL = "claude-opus-5-5"
CLASSIFIER_MODEL = "claude-haiku-5-5"

# A fresh nonce at the very front of the prefix, so each run starts cold
# instead of reading the cache a previous run left behind.
RUN_NONCE = uuid.uuid4().hex[:12]

EPHEMERAL = {"type": "ephemeral"}

TOOL_GUIDANCE = (
    "Use the location exactly as the user wrote it; do not translate place names. "
    "Dates are ISO 8601 in the location's local time zone. "
    "Resolve a relative date such as 'Saturday' to the next such date. "
    "Return metric units unless the user asked for imperial. "
    "Never call this tool twice for the same location and date in one turn. "
    "If the location is ambiguous, ask which one the user means instead of guessing. "
    "Mountain forecasts above 1,500 m often differ from the nearest town; "
    "prefer the trailhead's coordinates when the user names a trail. "
    "Open-Meteo data is CC-BY; cite it as Open-Meteo when you show numbers. "
)


def _tool(name: str, purpose: str, extra: str = "") -> dict:
    return {
        "name": name,
        "description": f"{purpose} {TOOL_GUIDANCE * 2}{extra}",
        "input_schema": {
            "type": "object",
            "properties": {
                "location": {"type": "string", "description": "Place name or 'lat,lon'."},
                "date": {"type": "string", "description": "ISO 8601 date."},
            },
            "required": ["location", "date"],
        },
    }


def build_tools(edited: bool = False) -> list[dict]:
    tools = [
        _tool("get_forecast", f"[lab run {RUN_NONCE}] Daily temperature, rain, and wind."),
        _tool("get_hourly", "Hourly temperature, rain probability, and gusts for one day."),
        _tool("get_air_quality", "Air quality index and pollen levels for one day."),
        _tool(
            "get_alerts",
            "Official weather warnings in effect for a location and date.",
            " Prefer the national weather service's wording." if edited else "",
        ),
    ]
    tools[-1] = {**tools[-1], "cache_control": EPHEMERAL}
    return tools


RULE_TOPICS = [
    ("a hike", "rain, gusts, and thunderstorm risk for the whole time window"),
    ("a summit", "freezing level, wind at altitude, and visibility"),
    ("a picnic", "hourly rain probability and temperature"),
    ("cycling", "wind direction relative to the route and gusts"),
    ("air quality", "the air quality index and pollen for sensitive users"),
    ("travel", "alerts along the route as well as at the destination"),
    ("a multi-day trip", "each day separately, never an average"),
    ("children", "heat and cold thresholds suitable for children"),
]

SYSTEM_TEXT = "You are the orchestrator of a weather assistant for hikers.\n\n" + "\n".join(
    f"Rule {i}: When the question concerns {topic}, check {check} before answering, "
    "state your confidence plainly, and say which tool result the answer rests on."
    for i, (topic, check) in enumerate(RULE_TOPICS * 5, start=1)
)

SPECIALIST_NOTE = "You are now the hiking specialist."


def build_system(edited: bool = False) -> list[dict]:
    text = SYSTEM_TEXT + (f"\n\n{SPECIALIST_NOTE}" if edited else "")
    return [{"type": "text", "text": text, "cache_control": EPHEMERAL}]


FIRST_ANSWER = (
    "For a Saturday hike near Innsbruck, check these, in this order. "
    + (
        "First the afternoon thunderstorm risk, since alpine storms build after midday. "
        "Then gusts on exposed ridges, then the freezing level above 2,000 m, "
        "then valley fog in the morning, which usually lifts by ten. "
    )
    * 6
)

SECOND_ANSWER = (
    "Morning rain usually means wet roots and slippery limestone. Start later, "
    "pick a trail with less exposure, and recheck the hourly forecast at seven."
)

HISTORY = [
    {"role": "user", "content": "I'm planning a hike near Innsbruck on Saturday. What to check?"},
    {"role": "assistant", "content": FIRST_ANSWER},
    {"role": "user", "content": "And if it rains in the morning?"},
    {
        "role": "assistant",
        "content": [{"type": "text", "text": SECOND_ANSWER, "cache_control": EPHEMERAL}],
    },
]

FIRST_QUESTION = "Which tool do you call first?"
SECOND_QUESTION = "What about wind on the ridge?"


def messages(new_turn: str, system_note: str | None = None) -> list[dict]:
    extra = [{"role": "system", "content": system_note}] if system_note else []
    return [*HISTORY, *extra, {"role": "user", "content": new_turn}]


def base_request(new_turn: str = FIRST_QUESTION) -> dict:
    return {"tools": build_tools(), "system": build_system(), "messages": messages(new_turn)}


CLASSIFIER_REQUEST = {
    "system": "Classify the message as forecast, travel, or other. Reply with one word.",
    "messages": [{"role": "user", "content": SECOND_QUESTION}],
}

STEPS = [
    ("0  warm up", MAIN_MODEL, base_request()),
    ("1  append a new user turn", MAIN_MODEL, base_request(SECOND_QUESTION)),
    # "none" rather than forcing a tool: a forced tool_choice is rejected when thinking is on.
    (
        "2  turn tools off with tool_choice",
        MAIN_MODEL,
        {**base_request(), "tool_choice": {"type": "none"}},
    ),
    (
        "3  edit the top-level system prompt",
        MAIN_MODEL,
        {**base_request(), "system": build_system(edited=True)},
    ),
    (
        "4  append a role=system message",
        MAIN_MODEL,
        {**base_request(), "messages": messages(FIRST_QUESTION, SPECIALIST_NOTE)},
    ),
    (
        "5  edit one tool description",
        MAIN_MODEL,
        {**base_request(), "tools": build_tools(edited=True)},
    ),
    ("6a classifier request (Haiku)", CLASSIFIER_MODEL, CLASSIFIER_REQUEST),
    ("6b then the main conversation", MAIN_MODEL, base_request(SECOND_QUESTION)),
    ("7  same conversation sent to Opus", SWITCH_MODEL, base_request()),
]


def main() -> None:
    if not os.environ.get("ANTHROPIC_API_KEY"):
        sys.exit("Set ANTHROPIC_API_KEY first.")
    client = anthropic.Anthropic()

    print(f"run {RUN_NONCE}\n")
    print(f"{'step':<40}{'model':<20}{'write':>8}{'read':>8}{'fresh':>8}{'read %':>8}")
    base_read = None
    for name, model, request in STEPS:
        try:
            usage = client.messages.create(model=model, max_tokens=0, **request).usage
        except anthropic.BadRequestError as error:
            print(f"{name:<40}{model:<20}  rejected: {error.message}")
            continue
        read = usage.cache_read_input_tokens or 0
        write = usage.cache_creation_input_tokens or 0
        if name.startswith("1 "):
            base_read = read
        share = f"{100 * read / base_read:.0f}%" if base_read else ""
        print(f"{name:<40}{model:<20}{write:>8}{read:>8}{usage.input_tokens:>8}{share:>8}")

    print("\nwrite = tokens written to cache, read = tokens read from cache, fresh = uncached.")
    print("read % compares each step's cache read with step 1, which reuses the whole prefix.")


if __name__ == "__main__":
    main()
