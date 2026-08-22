"""Global deterministic-test isolation for the entire MaryV2 repository.

This file lives at the repository root so it also protects legacy/root-level
regression tests, not only tests under ``tests/``.

The developer runtime may have real provider credentials and persistent Mary
state. Deterministic tests must inherit neither accidentally. Individual tests
that intentionally exercise provider/path configuration may override these
values with ``monkeypatch`` inside the test.
"""

from __future__ import annotations

import pytest


_LIVE_PROVIDER_ENV = (
    "GROQ_API_KEY",
    "GEMINI_API_KEY",
    "GOOGLE_API_KEY",
    "OPENROUTER_API_KEY",
    "OPENAI_API_KEY",
)


@pytest.fixture(autouse=True)
def _isolate_test_runtime(monkeypatch, tmp_path):
    """Keep every pytest case offline and away from Mary's real persistent data."""

    for name in _LIVE_PROVIDER_ENV:
        monkeypatch.delenv(name, raising=False)

    # Host-specific fallback configuration in a personal .env must not silently
    # alter tests that expect defaults or install fake providers themselves.
    monkeypatch.delenv("MARY_LLM_FALLBACKS", raising=False)
    # Route order is host policy too. A personal .env may deliberately use a
    # cloud-first conversation profile; tests that need a specific route must
    # configure it explicitly instead of inheriting the developer machine.
    monkeypatch.delenv("MARY_LLM_CONVERSATION_ORDER", raising=False)

    # This is the key persistence boundary: every test gets its own private data
    # root. A forgotten tmp_path/chdir can no longer write relationship state,
    # agency state, directives, memory-adjacent files, or future persistent
    # subsystems into the developer's real data directory.
    monkeypatch.setenv("MARY_DATA_DIR", str(tmp_path / "maryv2_data"))
