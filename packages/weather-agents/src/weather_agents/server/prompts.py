"""Prompts: the weekend check and the trip comparison."""

from collections.abc import Callable
from datetime import date
from typing import Annotated

from mcp import MCPError
from mcp.server import MCPServer
from mcp.types import INVALID_PARAMS
from pydantic import Field

MAX_PLACES = 5
SEASONAL_REACH_MONTHS = 6
MONTHS = (
    "January",
    "February",
    "March",
    "April",
    "May",
    "June",
    "July",
    "August",
    "September",
    "October",
    "November",
    "December",
)

WEEKEND_CHECK = """\
<role>
You help the user decide which day of the coming weekend is better for time outdoors.
</role>

<instructions>
1. Ask the user where they are. Wait for the answer.
2. Call `geocode_search` with the place name. If it returns several places, show them with \
country and region and ask which one the user means.
3. Call `forecast` for the chosen place with `days` set to 10 and the default variables.
4. In the forecast table, find the rows whose `weekday` is Saturday and Sunday. The table is \
already in the place's local timezone. Use the first Saturday and the first Sunday in it. \
Today counts if it falls on the weekend.
5. Call `ensemble` for the same place with `days` set to 10. Read the `_std` columns for the \
same two dates.
6. Decide which of the two days is better for being outside, and say how sure the forecast is.
</instructions>

<rules>
- Take every number from tool results. Do not estimate weather from memory.
- A larger `_std` means the ensemble members disagree, so the forecast is less certain. \
Say so when the two days differ in certainty.
- If a tool returns an error, tell the user what failed and stop.
</rules>

<quality_criteria>
- The answer names both dates with their weekdays.
- It says which day is better and gives the temperature, precipitation, and wind that decide it.
- It states how sure the forecast is and why.
</quality_criteria>
"""

COMPARE_PLACES = """\
<role>
You help the user choose where to travel in a given month by comparing the climate of up to \
five places.
</role>

<instructions>
1. Split the text in `<places>` on commas to get the individual place names.
2. For each place, call `geocode_search` and use the first result. If the name is ambiguous, \
choose the most populous result and tell the user which one you chose.
3. For each place, call `historical` with `start_date` 1991-01-01, `end_date` 2020-12-31, and \
the default variables. It returns 12 rows, one per calendar month, that are the 30-year \
normals. Read the row whose `time` equals `<month_number>`.
4. If `<seasonal_months>` is a number, also call `seasonal` for each place with `months` set \
to that number. Read the row for the month in `<month>`, and report it as a low-confidence \
tendency against normal. If `<seasonal_months>` is none, skip this step.
5. Say which place suits the trip best and why.
</instructions>

<rules>
- Take every number from tool results. Do not estimate climate from memory.
- Label the seasonal part low-confidence every time you mention it, because it is a tendency \
and not a forecast for specific days.
- If a tool returns an error for one place, say so and continue with the others.
</rules>

<quality_criteria>
- Every place appears in the comparison with its temperature and precipitation normals.
- The answer picks one place and gives the figures behind the choice.
- Seasonal information, when present, is kept apart from the normals and labelled low-confidence.
</quality_criteria>
"""


def parse_month(value: str) -> int:
    """Accept 1 to 12 or an English month name, in full or in three letters."""
    text = value.strip().lower()
    if text.isascii() and text.isdigit() and 1 <= int(text) <= 12:
        return int(text)
    for number, name in enumerate(MONTHS, start=1):
        if text in (name.lower(), name[:3].lower()):
            return number
    raise MCPError(
        code=INVALID_PARAMS,
        message=f"Invalid argument 'month': {value!r} is not a month. "
        "Use 1 to 12 or an English month name.",
    )


def check_places(value: str) -> None:
    names = [name for name in value.split(",") if name.strip()]
    if not names:
        raise MCPError(
            code=INVALID_PARAMS,
            message="Invalid argument 'places': give 1 to 5 place names separated by commas.",
        )
    if len(names) > MAX_PLACES:
        raise MCPError(
            code=INVALID_PARAMS,
            message=f"Invalid argument 'places': got {len(names)} places, the maximum is "
            f"{MAX_PLACES}.",
        )


def register(mcp: MCPServer, today: Callable[[], date]) -> None:
    @mcp.prompt(title="Weekend check")
    def weekend_check() -> str:
        """Ask where the user is, then say which day of this weekend is better outside."""
        return WEEKEND_CHECK

    @mcp.prompt(title="Compare places for a trip")
    def compare_places(
        places: Annotated[str, Field(description="Up to 5 place names separated by commas.")],
        month: Annotated[
            str, Field(description="Month of the trip: 1 to 12 or an English month name.")
        ],
    ) -> str:
        """Compare the climate of up to 5 places for one month of the year."""
        check_places(places)
        number = parse_month(month)
        months_ahead = (number - today().month) % 12
        seasonal_months = str(months_ahead + 1) if months_ahead <= SEASONAL_REACH_MONTHS else "none"
        return (
            f"{COMPARE_PLACES}\n"
            "<context>\n"
            f"<places>{places}</places>\n"
            f"<month>{MONTHS[number - 1]}</month>\n"
            f"<month_number>{number:02d}</month_number>\n"
            f"<seasonal_months>{seasonal_months}</seasonal_months>\n"
            "</context>\n"
        )
