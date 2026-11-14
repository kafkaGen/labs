import os
from pathlib import Path

import pytest


@pytest.fixture(autouse=True)
def isolated_env(monkeypatch: pytest.MonkeyPatch, tmp_path: Path) -> Path:
    """Run each test in an empty directory with no agent settings in the environment.

    Without this, settings would pick up the developer's real key from the repo's `.env`.
    """
    for name in list(os.environ):
        if name == "ANTHROPIC_API_KEY" or name.startswith("WEATHER_AGENTS_"):
            monkeypatch.delenv(name)
    workdir = tmp_path / "work"
    workdir.mkdir()
    monkeypatch.chdir(workdir)
    return workdir
