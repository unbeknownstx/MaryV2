"""Device-local execution permissions for bounded Mary capability tasks."""
from __future__ import annotations

import json
from pathlib import Path
from threading import RLock
from typing import Any

_SAFE_CAPABILITIES = {"personal_search", "llm.ollama"}


def default_permission_path() -> Path:
    return Path.home() / ".maryv2" / "device_permissions.json"


class DeviceExecutionPermissions:
    """Persistent local-only allow-list. Default is deny-all."""

    def __init__(self, path: str | Path | None = None) -> None:
        self.path = Path(path).expanduser() if path else default_permission_path()
        self._lock = RLock()

    def allowed(self) -> set[str]:
        with self._lock:
            try:
                raw = json.loads(self.path.read_text(encoding="utf-8"))
            except (OSError, ValueError, TypeError):
                return set()
            values = raw.get("allowed_capabilities", []) if isinstance(raw, dict) else []
            return {
                str(value).strip().lower()
                for value in values
                if str(value).strip().lower() in _SAFE_CAPABILITIES
            }

    def is_allowed(self, capability: str) -> bool:
        return str(capability or "").strip().lower() in self.allowed()

    def allow(self, capability: str) -> dict[str, Any]:
        normalized = str(capability or "").strip().lower()
        if normalized not in _SAFE_CAPABILITIES:
            raise ValueError(f"Capability cannot be authorized by this build: {normalized}")
        values = self.allowed()
        values.add(normalized)
        self._write(values)
        return self.status()

    def deny(self, capability: str) -> dict[str, Any]:
        normalized = str(capability or "").strip().lower()
        values = self.allowed()
        values.discard(normalized)
        self._write(values)
        return self.status()

    def status(self) -> dict[str, Any]:
        values = sorted(self.allowed())
        return {
            "permission_file": str(self.path),
            "allowed_capabilities": values,
            "default": "deny",
            "supported": sorted(_SAFE_CAPABILITIES),
        }

    def _write(self, values: set[str]) -> None:
        with self._lock:
            self.path.parent.mkdir(parents=True, exist_ok=True)
            payload = {
                "version": "13.2",
                "allowed_capabilities": sorted(values),
                "policy": "local device opt-in; no shell or arbitrary command execution",
            }
            self.path.write_text(json.dumps(payload, indent=2), encoding="utf-8")
