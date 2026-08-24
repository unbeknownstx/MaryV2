"""Global deterministic-test isolation for MaryV2.

This module installs process isolation while pytest is loading its initial
``conftest.py`` files, before test-module collection can import
``mary.core.config``.  That ordering matters because configuration performs
dotenv discovery at import time and Mary loads persistent character state in
its constructor.

Every pytest process therefore receives a fresh, bounded system-temporary data
root, a deliberately nonexistent dotenv target, an in-memory reservoir, and a
temporary pytest/cache root.  The original process environment is restored
exactly when pytest tears down.
"""

from __future__ import annotations

import atexit
import os
from pathlib import Path
import shutil
import sys
import tempfile


_ISOLATION_PREFIX = "maryv2-pytest-session-"
_LIVE_PROVIDER_ENV = (
    "GROQ_API_KEY",
    "GEMINI_API_KEY",
    "GOOGLE_API_KEY",
    "OPENROUTER_API_KEY",
    "OPENAI_API_KEY",
)
_ISOLATED_ENV = (
    "MARY_DATA_DIR",
    "MARY_ENV_FILE",
    "MARY_RESERVOIR_STORAGE",
    "MARY_LLM_FALLBACKS",
    "PYTEST_DEBUG_TEMPROOT",
    "PYTEST_ADDOPTS",
    *_LIVE_PROVIDER_ENV,
)


if "mary.core.config" in sys.modules:
    raise RuntimeError(
        "mary.core.config was imported before deterministic pytest state isolation"
    )


_SYSTEM_TEMP_ROOT = Path(tempfile.gettempdir()).resolve()
_SESSION_ROOT = Path(tempfile.mkdtemp(prefix=_ISOLATION_PREFIX)).resolve()
_SESSION_DATA_ROOT = _SESSION_ROOT / "state"
_SESSION_PYTEST_ROOT = _SESSION_ROOT / "pytest"
_SESSION_ENV_FILE = _SESSION_ROOT / "no-live-config"
_PREVIOUS_ENVIRONMENT = {name: os.environ.get(name) for name in _ISOLATED_ENV}
_ENVIRONMENT_RESTORED = False
_ROOT_REMOVED = False
_EXPLICIT_LIVE_TESTS = os.environ.get("MARY_RUN_LIVE_TESTS", "").strip().lower() in {
    "1",
    "true",
    "yes",
    "on",
}


def _validate_session_root() -> Path:
    """Return the cleanup target only when it is a direct safe temp child."""

    candidate = _SESSION_ROOT.resolve()
    if candidate.parent != _SYSTEM_TEMP_ROOT:
        raise RuntimeError("refusing pytest cleanup outside the direct system temp root")
    if not candidate.name.startswith(_ISOLATION_PREFIX):
        raise RuntimeError("refusing pytest cleanup without the isolation prefix")
    if candidate.is_symlink():
        raise RuntimeError("refusing recursive cleanup of a pytest isolation symlink")
    is_junction = getattr(candidate, "is_junction", None)
    if callable(is_junction) and is_junction():
        raise RuntimeError("refusing recursive cleanup of a pytest isolation junction")
    return candidate


def _restore_test_environment() -> None:
    """Exactly restore environment values and remove only the validated root."""

    global _ENVIRONMENT_RESTORED, _ROOT_REMOVED
    if not _ENVIRONMENT_RESTORED:
        for name, value in _PREVIOUS_ENVIRONMENT.items():
            if value is None:
                os.environ.pop(name, None)
            else:
                os.environ[name] = value
        _ENVIRONMENT_RESTORED = True

    if not _ROOT_REMOVED:
        if _SESSION_ROOT.exists():
            shutil.rmtree(_validate_session_root())
        _ROOT_REMOVED = True


_SESSION_DATA_ROOT.mkdir(parents=True, exist_ok=False)
_SESSION_PYTEST_ROOT.mkdir(parents=True, exist_ok=False)
if _SESSION_ENV_FILE.exists():
    raise RuntimeError("pytest isolation requires a nonexistent MARY_ENV_FILE target")

# Explicit live-test mode may inherit credentials that the caller deliberately
# exported.  It still cannot read the repository .env or persistent data.
if not _EXPLICIT_LIVE_TESTS:
    for _name in _LIVE_PROVIDER_ENV:
        os.environ.pop(_name, None)
    os.environ.pop("MARY_LLM_FALLBACKS", None)
os.environ["MARY_DATA_DIR"] = str(_SESSION_DATA_ROOT)
os.environ["MARY_ENV_FILE"] = str(_SESSION_ENV_FILE)
os.environ["MARY_RESERVOIR_STORAGE"] = "memory"
os.environ["PYTEST_DEBUG_TEMPROOT"] = str(_SESSION_PYTEST_ROOT)
os.environ["PYTEST_ADDOPTS"] = "-p no:cacheprovider"

# Resolve the configured root now, before collection can construct Mary.  The
# import is intentionally below all state/dotenv overrides.
from mary.core.config import Config as _IsolationConfig

if _IsolationConfig().paths.data.resolve() != _SESSION_DATA_ROOT.resolve():
    raise RuntimeError("pytest Config resolved a non-isolated data root")
if _SESSION_ENV_FILE.exists():
    raise RuntimeError("pytest MARY_ENV_FILE target must remain nonexistent")
atexit.register(_restore_test_environment)

# Import pytest only after Mary's process environment is isolated.  The hook
# ordering keeps cache relocation after cache-plugin setup and cleanup after
# cache-plugin teardown.
import pytest


@pytest.hookimpl(trylast=True)
def pytest_configure(config) -> None:
    """Relocate an already-loaded cache plugin away from the repository."""

    cache = getattr(config, "cache", None)
    if cache is not None:
        cache._cachedir = _SESSION_ROOT / "pytest-cache"


@pytest.hookimpl(trylast=True)
def pytest_unconfigure(config) -> None:
    """Restore the process even when pytest is embedded instead of executed."""

    del config
    try:
        _restore_test_environment()
    except PermissionError:
        # Windows plugins may still be releasing a cache/temp handle during
        # unconfigure.  Environment restoration already happened; the
        # registered atexit callback safely retries the validated cleanup once
        # all pytest/plugin teardown has completed.
        pass
