"""Fakes and builders for the agent loop and runtime tests."""

from weather_agents.settings import Settings


def make_settings(**overrides: object) -> Settings:
    """Settings that ignore `.env` and carry a dummy API key."""
    return Settings(_env_file=None, anthropic_api_key="test-key", **overrides)
