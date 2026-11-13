from pathlib import Path

import pytest

FIXTURES = Path(__file__).parent / "fixtures"
GOLDEN = Path(__file__).parent / "golden"


@pytest.fixture
def fx():
    """Return the path of a hand-made fixture file."""

    def get(name: str) -> Path:
        return FIXTURES / name

    return get


@pytest.fixture(autouse=True)
def _clean_language_env(monkeypatch):
    """Tests must not depend on the developer's locale."""
    for name in ("SPEAKERJOIN_LANG", "LC_ALL", "LC_MESSAGES", "LANG"):
        monkeypatch.delenv(name, raising=False)
