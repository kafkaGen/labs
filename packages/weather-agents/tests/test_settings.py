import pytest
from pydantic import ValidationError

from weather_agents.settings import PACKAGE_ROOT, Settings


def test_the_defaults(monkeypatch):
    monkeypatch.setenv("ANTHROPIC_API_KEY", "key")
    settings = Settings(_env_file=None)
    assert settings.model == "claude-haiku-5-5"
    assert settings.effort == "low"
    assert settings.thinking is True
    assert settings.max_tokens == 32_000
    assert settings.fast_mode is False
    assert settings.mcp_config == PACKAGE_ROOT / "mcp.stdio.json"
    assert settings.log_level == "INFO"
    assert settings.log_truncate == 200
    assert settings.anthropic_api_key.get_secret_value() == "key"


def test_prefixed_environment_variables_override_the_defaults(monkeypatch):
    monkeypatch.setenv("ANTHROPIC_API_KEY", "key")
    monkeypatch.setenv("WEATHER_AGENTS_MODEL", "claude-sonnet-5-5")
    monkeypatch.setenv("WEATHER_AGENTS_EFFORT", "high")
    monkeypatch.setenv("WEATHER_AGENTS_THINKING", "false")
    monkeypatch.setenv("WEATHER_AGENTS_MCP_CONFIG", "mcp.http.json")
    settings = Settings(_env_file=None)
    assert settings.model == "claude-sonnet-5-5"
    assert settings.effort == "high"
    assert settings.thinking is False
    assert settings.mcp_config == PACKAGE_ROOT / "mcp.http.json"


def test_an_absolute_mcp_config_is_kept(monkeypatch, tmp_path):
    monkeypatch.setenv("ANTHROPIC_API_KEY", "key")
    settings = Settings(_env_file=None, mcp_config=tmp_path / "mcp.json")
    assert settings.mcp_config == tmp_path / "mcp.json"


def test_the_api_key_is_read_without_the_prefix(monkeypatch):
    monkeypatch.delenv("ANTHROPIC_API_KEY", raising=False)
    monkeypatch.setenv("WEATHER_AGENTS_ANTHROPIC_API_KEY", "wrong")
    with pytest.raises(ValidationError, match="ANTHROPIC_API_KEY"):
        Settings(_env_file=None)


def test_an_unknown_effort_fails_naming_the_field(monkeypatch):
    monkeypatch.setenv("ANTHROPIC_API_KEY", "key")
    monkeypatch.setenv("WEATHER_AGENTS_EFFORT", "extreme")
    with pytest.raises(ValidationError, match="effort"):
        Settings(_env_file=None)


def test_a_zero_max_tokens_fails_naming_the_field(monkeypatch):
    monkeypatch.setenv("ANTHROPIC_API_KEY", "key")
    with pytest.raises(ValidationError, match="max_tokens"):
        Settings(_env_file=None, max_tokens=0)


def test_the_key_never_shows_in_the_repr(monkeypatch):
    monkeypatch.setenv("ANTHROPIC_API_KEY", "very-secret")
    assert "very-secret" not in repr(Settings(_env_file=None))
