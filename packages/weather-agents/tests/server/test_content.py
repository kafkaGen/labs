import re

import pytest

from weather_agents.server.resources import CONTENT_DIR, ENDPOINTS

GUIDE_SECTIONS = [
    "Where the data comes from",
    "Refresh and trust",
    "Shared API conventions",
    "Which endpoint answers what",
    "What Open-Meteo cannot answer",
    "Attribution and terms",
]
ENDPOINT_SECTIONS = [
    "What it answers",
    "Sources and models",
    "Trust and limits",
    "Variables",
    "Argument tips",
]
SOURCE_LINE = re.compile(r"^Source: https://open-meteo\.com/\S+$", re.MULTILINE)


def sections(text: str) -> dict[str, str]:
    parts = re.split(r"^## (.+)$", text, flags=re.MULTILINE)
    return dict(zip(parts[1::2], parts[2::2], strict=True))


def test_the_guide_has_the_sections_the_scope_lists():
    text = (CONTENT_DIR / "guide.md").read_text(encoding="utf-8")
    assert list(sections(text)) == GUIDE_SECTIONS


@pytest.mark.parametrize("endpoint", ENDPOINTS)
def test_each_endpoint_guide_has_the_five_parts(endpoint):
    text = (CONTENT_DIR / "endpoints" / f"{endpoint}.md").read_text(encoding="utf-8")
    assert list(sections(text)) == ENDPOINT_SECTIONS


@pytest.mark.parametrize("name", ["guide", *[f"endpoints/{e}" for e in ENDPOINTS]])
def test_every_section_ends_with_an_open_meteo_source_line(name):
    text = (CONTENT_DIR / f"{name}.md").read_text(encoding="utf-8")
    for title, body in sections(text).items():
        assert SOURCE_LINE.search(body), f"{name}: section '{title}' has no Source line"


def test_there_are_no_endpoint_files_beyond_the_ten():
    files = {path.stem for path in (CONTENT_DIR / "endpoints").glob("*.md")}
    assert files == set(ENDPOINTS)
