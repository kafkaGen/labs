import os
from pathlib import Path

import pytest
from pydantic import ValidationError

from weather_agents.settings import (
    ForbiddenOverrideError,
    LogLevel,
    Settings,
    UnknownSettingError,
)


@pytest.fixture(autouse=True)
def clean_env(monkeypatch: pytest.MonkeyPatch, tmp_path: Path) -> None:
    # No real .env and no WEATHER_AGENTS_* or API key from the developer's shell.
    monkeypatch.chdir(tmp_path)
    for name in list(os.environ):
        if name.startswith("WEATHER_AGENTS_") or name == "ANTHROPIC_API_KEY":
            monkeypatch.delenv(name)


def test_defaults():
    settings = Settings()
    assert settings.model == "claude-haiku-5-5"
    assert settings.deadline_seconds == 120
    assert settings.usd_cap == 0.10
    assert settings.max_tokens == 16_000
    assert settings.mcp_config == Path("mcp.stdio.json")
    assert settings.log_level is LogLevel.INFO
    assert settings.log_truncate_chars == 200
    assert settings.anthropic_api_key is None


def test_environment_overrides_a_default(monkeypatch: pytest.MonkeyPatch):
    monkeypatch.setenv("WEATHER_AGENTS_USD_CAP", "0.05")
    assert Settings().usd_cap == 0.05


def test_dotenv_is_read_and_the_environment_wins_over_it(
    monkeypatch: pytest.MonkeyPatch, tmp_path: Path
):
    (tmp_path / ".env").write_text("WEATHER_AGENTS_DEADLINE_SECONDS=60\nANTHROPIC_API_KEY=sk-env\n")
    assert Settings().deadline_seconds == 60
    monkeypatch.setenv("WEATHER_AGENTS_DEADLINE_SECONDS", "45")
    settings = Settings()
    assert settings.deadline_seconds == 45
    assert settings.anthropic_api_key is not None
    assert settings.anthropic_api_key.get_secret_value() == "sk-env"


def test_a_negative_cap_fails_naming_the_field(monkeypatch: pytest.MonkeyPatch):
    monkeypatch.setenv("WEATHER_AGENTS_USD_CAP", "-1")
    with pytest.raises(ValidationError, match="usd_cap"):
        Settings()


def test_an_unknown_log_level_fails_naming_the_field(monkeypatch: pytest.MonkeyPatch):
    monkeypatch.setenv("WEATHER_AGENTS_LOG_LEVEL", "LOUD")
    with pytest.raises(ValidationError, match="log_level"):
        Settings()


def test_an_override_wins_over_the_environment(monkeypatch: pytest.MonkeyPatch):
    monkeypatch.setenv("WEATHER_AGENTS_DEADLINE_SECONDS", "60")
    settings = Settings().with_overrides(deadline_seconds=30)
    assert settings.deadline_seconds == 30


def test_an_override_keeps_the_other_fields_and_the_key(monkeypatch: pytest.MonkeyPatch):
    monkeypatch.setenv("ANTHROPIC_API_KEY", "sk-env")
    monkeypatch.setenv("WEATHER_AGENTS_USD_CAP", "0.05")
    settings = Settings().with_overrides(deadline_seconds=30)
    assert settings.usd_cap == 0.05
    assert settings.anthropic_api_key is not None
    assert settings.anthropic_api_key.get_secret_value() == "sk-env"


def test_a_zero_deadline_override_fails_naming_the_field():
    with pytest.raises(ValidationError, match="deadline_seconds"):
        Settings().with_overrides(deadline_seconds=0)


def test_an_override_of_an_unknown_field_fails():
    with pytest.raises(UnknownSettingError, match="usd_kap"):
        Settings().with_overrides(usd_kap=1)


@pytest.mark.parametrize("name", ["anthropic_api_key", "ANTHROPIC_API_KEY"])
def test_the_api_key_cannot_be_overridden(name: str):
    with pytest.raises(ForbiddenOverrideError, match="anthropic_api_key"):
        Settings().with_overrides(**{name: "sk-run"})


def test_the_key_never_shows_in_the_settings_repr(monkeypatch: pytest.MonkeyPatch):
    monkeypatch.setenv("ANTHROPIC_API_KEY", "sk-secret")
    assert "sk-secret" not in repr(Settings())


def test_other_tools_keys_in_a_shared_dotenv_are_ignored(tmp_path: Path):
    (tmp_path / ".env").write_text("GITHUB_TOKEN=ghp-x\nOTHER_KEY=y\nANTHROPIC_API_KEY=sk-env\n")
    settings = Settings()
    assert settings.anthropic_api_key is not None
    assert not hasattr(settings, "github_token")


def test_a_validation_error_never_echoes_the_value(monkeypatch: pytest.MonkeyPatch):
    monkeypatch.setenv("WEATHER_AGENTS_USD_CAP", "secret-looking-value")
    with pytest.raises(ValidationError) as caught:
        Settings()
    assert "usd_cap" in str(caught.value)
    assert "secret-looking-value" not in str(caught.value)
