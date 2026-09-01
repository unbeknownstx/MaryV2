"""Early Qt WebEngine process configuration for Mary desktop surfaces.

Qt WebEngine consumes Chromium command-line flags when its process is first
initialized.  Mary currently loads the trusted Vite production shell from a
``file://`` URL so it can also play the temporary ``file://`` audio files
staged by :mod:`mary.desktop.audio_cache` without adding another web server or
transport layer.

On macOS with Qt/Chromium 6.11, ES-module and stylesheet subresources from the
same local build can otherwise be treated as a unique/null origin and rejected
before Mary's JavaScript boot code executes.  ``--allow-file-access-from-files``
restores same-machine file-to-file loading for this trusted desktop shell.

This module deliberately has no PySide imports.  Call
:func:`configure_qtwebengine` *before* importing ``QtWebEngine`` classes.
"""

from __future__ import annotations

import os
import shlex
import sys

_FILE_ACCESS_FLAG = "--allow-file-access-from-files"


def _flag_tokens(value: str) -> list[str]:
    """Return Chromium flag tokens without failing on an imperfect env value."""

    if not value.strip():
        return []
    try:
        return shlex.split(value)
    except ValueError:
        # Preserve startup even if a user supplied unmatched quoting.  We only
        # need a conservative duplicate check before appending our own flag.
        return value.split()


def configure_qtwebengine(*, platform: str | None = None) -> str:
    """Apply Mary desktop's required early WebEngine flags.

    The macOS-only file-access flag is intentionally narrow: it does not disable
    Chromium web security and it does not affect Mary Core/network authority.
    Existing ``QTWEBENGINE_CHROMIUM_FLAGS`` values are preserved verbatim.

    Returns the effective flag string, which also makes this helper easy to
    verify in isolation without importing PySide6.
    """

    effective_platform = sys.platform if platform is None else str(platform)
    current = os.environ.get("QTWEBENGINE_CHROMIUM_FLAGS", "").strip()

    if effective_platform != "darwin":
        return current

    if _FILE_ACCESS_FLAG not in _flag_tokens(current):
        current = f"{current} {_FILE_ACCESS_FLAG}".strip()
        os.environ["QTWEBENGINE_CHROMIUM_FLAGS"] = current

    return current


__all__ = ["configure_qtwebengine"]
