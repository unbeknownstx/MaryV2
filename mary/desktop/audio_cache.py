"""Finite temporary audio transport cache for Mary Desktop.

QWebChannel JSON is a poor transport for a large base64 MP3/WAV payload.  The
12.12.2 desktop stages synthesized bytes into a bounded temporary directory and
sends a bounded local URL to the browser instead.  The cache is presentation-only:
it is not memory, is never indexed by Mary's reservoir, and is deleted on
normal desktop shutdown / bounded by a small file count if the process exits
abruptly.
"""
from __future__ import annotations

import base64
from pathlib import Path
import tempfile
from threading import RLock
import time
from typing import Any, Callable
from uuid import uuid4


class DesktopAudioCache:
    def __init__(
        self,
        root: str | Path | None = None,
        *,
        max_files: int = 12,
        public_url_builder: Callable[[Path], str] | None = None,
    ) -> None:
        base = Path(root) if root is not None else Path(tempfile.gettempdir()) / "MaryV2" / "voice-cache"
        self.root = base.expanduser().resolve()
        self.root.mkdir(parents=True, exist_ok=True)
        self.max_files = max(3, min(64, int(max_files)))
        self._lock = RLock()
        self._owned: set[Path] = set()
        self._public_url_builder = public_url_builder
        self._prune()

    def set_public_url_builder(
        self, builder: Callable[[Path], str] | None
    ) -> None:
        """Route staged audio through the desktop loopback origin when set."""
        with self._lock:
            self._public_url_builder = builder

    def stage(self, payload: dict[str, Any]) -> dict[str, Any]:
        """Return a copy whose audio uses the configured local transport when possible."""
        output = dict(payload or {})
        encoded = str(output.get("audio_base64") or "").strip()
        if not encoded:
            return output
        try:
            audio = base64.b64decode(encoded, validate=True)
        except Exception:
            output["audio_transport"] = "base64"
            return output
        if not audio:
            return output

        fmt = str(output.get("format") or "mp3").lower().strip()
        suffix = ".wav" if fmt == "wav" else ".mp3"
        path = self.root / f"mary-{time.time_ns()}-{uuid4().hex[:8]}{suffix}"
        try:
            with self._lock:
                path.write_bytes(audio)
                self._owned.add(path)
                if self._public_url_builder is not None:
                    output["audio_url"] = self._public_url_builder(path)
                    output["audio_transport"] = "loopback_url"
                else:
                    output["audio_url"] = path.as_uri()
                    output["audio_transport"] = "file_url"
                output.pop("audio_base64", None)
                self._prune_locked()
        except Exception:
            output["audio_transport"] = "base64"
        return output

    def cleanup(self) -> None:
        with self._lock:
            for path in list(self._owned):
                try:
                    path.unlink(missing_ok=True)
                except Exception:
                    pass
            self._owned.clear()
            self._prune_locked(keep=0)
            try:
                self.root.rmdir()
            except OSError:
                pass

    def _prune(self) -> None:
        with self._lock:
            self._prune_locked()

    def _prune_locked(self, *, keep: int | None = None) -> None:
        limit = self.max_files if keep is None else max(0, int(keep))
        try:
            files = sorted(
                (item for item in self.root.iterdir() if item.is_file() and item.suffix.lower() in {".mp3", ".wav"}),
                key=lambda item: item.stat().st_mtime,
                reverse=True,
            )
        except OSError:
            return
        for path in files[limit:]:
            try:
                path.unlink(missing_ok=True)
            except OSError:
                continue
            self._owned.discard(path)
