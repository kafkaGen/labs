from pathlib import Path

import pytest

from weather_agents.settings import DEFAULT_MCP_CONFIG, SettingsError, load_settings

KEY = "sk-test-not-a-real-key"


def test_defaults_need_only_the_key(monkeypatch: pytest.MonkeyPatch):
    monkeypatch.setenv("ANTHROPIC_API_KEY", KEY)

    settings = load_settings()

    assert settings.model == "claude-haiku-5-5"
    assert settings.max_tokens == 16_000
    assert settings.mcp_config == DEFAULT_MCP_CONFIG
    assert settings.anthropic_api_key.get_secret_value() == KEY


def test_the_default_mcp_config_is_the_package_stdio_file():
    assert DEFAULT_MCP_CONFIG.name == "mcp.stdio.json"
    assert DEFAULT_MCP_CONFIG.is_file()


def test_the_environment_beats_the_default(monkeypatch: pytest.MonkeyPatch):
    monkeypatch.setenv("ANTHROPIC_API_KEY", KEY)
    monkeypatch.setenv("WEATHER_AGENTS_MODEL", "claude-sonnet-5-5")

    assert load_settings().model == "claude-sonnet-5-5"


def test_an_override_beats_the_environment(monkeypatch: pytest.MonkeyPatch):
    monkeypatch.setenv("ANTHROPIC_API_KEY", KEY)
    monkeypatch.setenv("WEATHER_AGENTS_MODEL", "claude-sonnet-5-5")

    assert load_settings(model="claude-opus-5-5").model == "claude-opus-5-5"


def test_the_key_can_be_overridden_by_field_name():
    settings = load_settings(anthropic_api_key=KEY)

    assert settings.anthropic_api_key.get_secret_value() == KEY


def test_values_load_from_dotenv(isolated_env: Path):
    (isolated_env / ".env").write_text(
        f"ANTHROPIC_API_KEY={KEY}\nWEATHER_AGENTS_MAX_TOKENS=2048\nUNRELATED_KEY=x\n"
    )

    settings = load_settings()

    assert settings.anthropic_api_key.get_secret_value() == KEY
    assert settings.max_tokens == 2048


def test_the_environment_beats_dotenv(isolated_env: Path, monkeypatch: pytest.MonkeyPatch):
    (isolated_env / ".env").write_text(f"ANTHROPIC_API_KEY={KEY}\nWEATHER_AGENTS_MODEL=a\n")
    monkeypatch.setenv("WEATHER_AGENTS_MODEL", "b")

    assert load_settings().model == "b"


def test_the_nearest_dotenv_up_the_tree_is_used(
    isolated_env: Path, monkeypatch: pytest.MonkeyPatch
):
    (isolated_env / ".env").write_text(f"ANTHROPIC_API_KEY={KEY}\n")
    nested = isolated_env / "a" / "b"
    nested.mkdir(parents=True)
    monkeypatch.chdir(nested)

    assert load_settings().anthropic_api_key.get_secret_value() == KEY


def test_a_bad_max_tokens_names_the_field():
    with pytest.raises(SettingsError, match="max_tokens"):
        load_settings(anthropic_api_key=KEY, max_tokens=-5)


def test_a_missing_key_names_the_field():
    with pytest.raises(SettingsError, match="ANTHROPIC_API_KEY"):
        load_settings()


def test_a_missing_mcp_config_names_the_field(tmp_path: Path):
    with pytest.raises(SettingsError, match="mcp_config"):
        load_settings(anthropic_api_key=KEY, mcp_config=tmp_path / "nope.json")


def test_errors_never_show_the_key(monkeypatch: pytest.MonkeyPatch):
    monkeypatch.setenv("ANTHROPIC_API_KEY", KEY)

    with pytest.raises(SettingsError) as caught:
        load_settings(max_tokens="many")

    assert KEY not in str(caught.value)
    assert "many" not in str(caught.value)


def test_printing_settings_hides_the_key():
    settings = load_settings(anthropic_api_key=KEY)

    assert KEY not in repr(settings)
    assert KEY not in str(settings)
