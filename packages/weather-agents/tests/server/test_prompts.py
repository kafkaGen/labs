import pytest
from mcp import MCPError
from mcp.types import INVALID_PARAMS

pytestmark = pytest.mark.anyio

# The fixture clock is 2026-10-03, so October is month 0 ahead and March is 5 ahead.


async def test_weekend_check_takes_no_arguments_and_tells_the_model_what_to_do(client):
    result = await client.get_prompt("weekend_check")
    text = result.messages[0].content.text
    assert result.messages[0].role == "user"
    for expected in ("geocode_search", "forecast", "ensemble", "weekday", "Saturday", "Sunday"):
        assert expected in text


async def compare(client, places: str, month: str) -> str:
    result = await client.get_prompt("compare_places", {"places": places, "month": month})
    return result.messages[0].content.text


async def test_compare_places_gives_the_model_the_places_the_month_and_the_seasonal_reach(client):
    text = await compare(client, "Lisbon, Athens", "March")
    assert "<places>Lisbon, Athens</places>" in text
    assert "<month>March</month>" in text
    assert "<month_number>03</month_number>" in text
    assert "<seasonal_months>6</seasonal_months>" in text
    assert "historical" in text
    assert "low-confidence" in text


async def test_compare_places_skips_the_seasonal_outlook_for_a_far_month(client):
    text = await compare(client, "Lisbon", "august")
    assert "<seasonal_months>none</seasonal_months>" in text


async def test_compare_places_accepts_numbers_and_three_letter_names(client):
    assert "<month>October</month>" in await compare(client, "Lisbon", "10")
    assert "<seasonal_months>1</seasonal_months>" in await compare(client, "Lisbon", "oct")


async def test_compare_places_refuses_more_than_five_places(client):
    with pytest.raises(MCPError) as caught:
        await compare(client, "a, b, c, d, e, f", "March")
    assert caught.value.code == INVALID_PARAMS
    assert "places" in caught.value.message


async def test_compare_places_refuses_an_empty_list(client):
    with pytest.raises(MCPError) as caught:
        await compare(client, " , ", "March")
    assert "places" in caught.value.message


async def test_compare_places_refuses_a_month_that_is_not_a_month(client):
    with pytest.raises(MCPError) as caught:
        await compare(client, "Lisbon", "Smarch")
    assert caught.value.code == INVALID_PARAMS
    assert "month" in caught.value.message
