"""Small atomic JSON persistence primitives for MaryV2 continuity state."""
from __future__ import annotations

import json
import os
import tempfile
from copy import deepcopy
from pathlib import Path
from threading import RLock
from typing import Any, Callable


class AtomicJsonStore:
    """Thread-safe JSON document store with atomic replacement."""

    def __init__(self, path: Path, *, default: dict[str, Any]) -> None:
        self.path = Path(path)
        self._default = deepcopy(default)
        self._lock = RLock()
        self._data = deepcopy(default)
        self.load()

    def load(self) -> dict[str, Any]:
        with self._lock:
            if not self.path.exists():
                self._data = deepcopy(self._default)
                return deepcopy(self._data)
            try:
                raw = json.loads(self.path.read_text(encoding="utf-8"))
                self._data = raw if isinstance(raw, dict) else deepcopy(self._default)
            except (OSError, ValueError, TypeError):
                self._data = deepcopy(self._default)
            return deepcopy(self._data)

    def snapshot(self) -> dict[str, Any]:
        with self._lock:
            return deepcopy(self._data)

    def replace(self, payload: dict[str, Any]) -> dict[str, Any]:
        with self._lock:
            self._data = deepcopy(payload)
            self._write_locked()
            return deepcopy(self._data)

    def mutate(self, mutator: Callable[[dict[str, Any]], Any]) -> dict[str, Any]:
        with self._lock:
            working = deepcopy(self._data)
            result = mutator(working)
            if isinstance(result, dict):
                working = result
            self._data = working
            self._write_locked()
            return deepcopy(self._data)

    def _write_locked(self) -> None:
        self.path.parent.mkdir(parents=True, exist_ok=True)
        fd, temp_name = tempfile.mkstemp(
            prefix=f".{self.path.name}.", suffix=".tmp", dir=str(self.path.parent)
        )
        try:
            with os.fdopen(fd, "w", encoding="utf-8") as handle:
                json.dump(self._data, handle, ensure_ascii=False, indent=2, sort_keys=True)
                handle.flush()
                os.fsync(handle.fileno())
            os.replace(temp_name, self.path)
        finally:
            try:
                if os.path.exists(temp_name):
                    os.unlink(temp_name)
            except OSError:
                pass
