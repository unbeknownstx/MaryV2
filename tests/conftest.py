"""Session-wide deterministic test isolation for MaryV2.

This file intentionally establishes a fresh temporary data/config boundary at
import time, before tests import ``mary.core.config``.  The normal developer
runtime may use the repository's real .env and persistent data, but the test
suite must never inherit them implicitly.
"""
from __future__ import annotations

import atexit
import os
from pathlib import Path
import shutil
import tempfile

import pytest


_TRACKED_ENV = (
    "MARY_DATA_DIR",
    "MARY_ENV_FILE",
    "MARY_RESERVOIR_STORAGE",
    "PYTEST_DEBUG_TEMPROOT",
    "PYTEST_ADDOPTS",
    "GROQ_API_KEY",
    "GEMINI_API_KEY",
    "GOOGLE_API_KEY",
    "OPENROUTER_API_KEY",
    "OPENAI_API_KEY",
    "MARY_LLM_FALLBACKS",
)
_PROVIDER_ENV = (
    "GROQ_API_KEY",
    "GEMINI_API_KEY",
    "GOOGLE_API_KEY",
    "OPENROUTER_API_KEY",
    "OPENAI_API_KEY",
)
_PREVIOUS_ENV = {name: os.environ.get(name) for name in _TRACKED_ENV}
_SESSION_ROOT = Path(tempfile.mkdtemp(prefix="maryv2-pytest-session-")).resolve()
_SESSION_DATA_ROOT = _SESSION_ROOT / "state"
_SESSION_PYTEST_ROOT = _SESSION_ROOT / "pytest"
_SESSION_ENV_FILE = _SESSION_ROOT / "no-live-config"
_SESSION_DATA_ROOT.mkdir(parents=True, exist_ok=False)
_SESSION_PYTEST_ROOT.mkdir(parents=True, exist_ok=False)
if _SESSION_ENV_FILE.exists():
    raise RuntimeError("MaryV2 test isolation requires a nonexistent env file")

os.environ["MARY_DATA_DIR"] = str(_SESSION_DATA_ROOT)
os.environ["MARY_ENV_FILE"] = str(_SESSION_ENV_FILE)
os.environ["MARY_RESERVOIR_STORAGE"] = "memory"
os.environ["PYTEST_DEBUG_TEMPROOT"] = str(_SESSION_PYTEST_ROOT)
os.environ["PYTEST_ADDOPTS"] = "-p no:cacheprovider"

# Normal tests are forcibly offline.  Explicit live-test invocations may retain
# credentials deliberately exported by the caller, but still cannot load the
# project .env because MARY_ENV_FILE points at the nonexistent isolated path.
if os.environ.get("MARY_RUN_LIVE_TESTS") != "1":
    for _name in _PROVIDER_ENV:
        os.environ.pop(_name, None)
os.environ.pop("MARY_LLM_FALLBACKS", None)

_RESTORED = False


def _restore_test_environment() -> None:
    global _RESTORED
    if _RESTORED:
        return
    _RESTORED = True
    for name, value in _PREVIOUS_ENV.items():
        if value is None:
            os.environ.pop(name, None)
        else:
            os.environ[name] = value
    # The root is ours and is bounded directly below the system temp folder.
    system_temp = Path(tempfile.gettempdir()).resolve()
    try:
        resolved = _SESSION_ROOT.resolve()
        if (
            resolved.parent == system_temp
            and resolved.name.startswith("maryv2-pytest-session-")
            and not resolved.is_symlink()
        ):
            shutil.rmtree(resolved, ignore_errors=True)
    except OSError:
        pass


atexit.register(_restore_test_environment)


def pytest_sessionfinish(session, exitstatus):  # noqa: ARG001
    _restore_test_environment()


@pytest.fixture(autouse=True)
def _keep_each_test_offline(monkeypatch):
    """Prevent a test from accidentally inheriting credentials added later."""
    if os.environ.get("MARY_RUN_LIVE_TESTS") == "1":
        return
    for name in _PROVIDER_ENV:
        monkeypatch.delenv(name, raising=False)
