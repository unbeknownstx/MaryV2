"""Global deterministic-test isolation for MaryV2.

The normal developer runtime may have real provider credentials in ``.env``.
The deterministic pytest suite must never inherit those credentials or a live
local Ollama service implicitly. Individual tests that intentionally exercise
provider configuration can opt in by setting the needed environment variables
with ``monkeypatch`` inside that test.
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
def _isolate_live_provider_environment(monkeypatch):
    """Keep deterministic tests offline regardless of the developer's .env."""

    for name in _LIVE_PROVIDER_ENV:
        monkeypatch.delenv(name, raising=False)

    # Host-specific fallback configuration in a personal .env must not silently
    # alter tests that expect MaryV2 defaults or an explicitly installed fake
    # provider. Tests that exercise fallback parsing set this themselves.
    monkeypatch.delenv("MARY_LLM_FALLBACKS", raising=False)