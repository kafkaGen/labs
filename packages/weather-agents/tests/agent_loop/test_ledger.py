from weather_agents.agent_loop.ledger import SourceLedger


def test_a_recorded_call_matches_with_the_same_name_and_arguments():
    ledger = SourceLedger()
    ledger.record_tool_call("open-meteo__forecast", {"latitude": 52.52, "longitude": 13.41})
    assert ledger.has_tool_call("open-meteo__forecast", '{"latitude": 52.52, "longitude": 13.41}')


def test_key_order_does_not_matter():
    ledger = SourceLedger()
    ledger.record_tool_call("open-meteo__forecast", {"latitude": 52.52, "longitude": 13.41})
    assert ledger.has_tool_call("open-meteo__forecast", '{"longitude": 13.41, "latitude": 52.52}')


def test_other_arguments_or_another_tool_do_not_match():
    ledger = SourceLedger()
    ledger.record_tool_call("open-meteo__forecast", {"latitude": 52.52, "longitude": 13.41})
    assert not ledger.has_tool_call("open-meteo__forecast", '{"latitude": 0, "longitude": 0}')
    assert not ledger.has_tool_call("open-meteo__marine", '{"latitude": 52.52, "longitude": 13.41}')


def test_invalid_json_does_not_match():
    ledger = SourceLedger()
    ledger.record_tool_call("open-meteo__forecast", {})
    assert not ledger.has_tool_call("open-meteo__forecast", "{not json")


def test_a_url_matches_only_once_recorded():
    ledger = SourceLedger()
    assert not ledger.has_url("https://open-meteo.com")
    ledger.record_url("https://open-meteo.com")
    assert ledger.has_url("https://open-meteo.com")
