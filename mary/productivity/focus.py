"""Persistent, cheap Focus With Mary session state."""
from __future__ import annotations
from datetime import datetime, timezone
from pathlib import Path
from typing import Any
from mary.runtime.persistence import atomic_write_json, load_json_recovering


def _now() -> datetime:
    return datetime.now(timezone.utc)


class FocusManager:
    def __init__(self, root: str | Path) -> None:
        self.root = Path(root); self.path = self.root / "focus.json"
        payload, _ = load_json_recovering(self.path)
        self.state = dict(payload) if isinstance(payload, dict) else {"active": False, "history": []}
        self.state.setdefault("active", False); self.state.setdefault("history", [])

    def save(self) -> bool:
        self.state["history"] = list(self.state.get("history", []))[-100:]
        return atomic_write_json(self.path, self.state)

    def start(self, minutes: int = 45, *, task: str = "") -> dict[str, Any]:
        minutes = max(5, min(240, int(minutes))); started = _now()
        self.state.update({"active": True, "task": " ".join(str(task).split())[:180], "minutes": minutes,
                           "started_at": started.isoformat(), "ends_at": (started.timestamp() + minutes * 60)})
        self.save(); return self.snapshot()

    def stop(self, *, completed: bool = True) -> dict[str, Any]:
        if self.state.get("active"):
            self.state.setdefault("history", []).append({"task": self.state.get("task", ""), "minutes": self.state.get("minutes", 0),
                "started_at": self.state.get("started_at"), "stopped_at": _now().isoformat(), "completed": bool(completed)})
        self.state.update({"active": False, "task": "", "started_at": None, "ends_at": None}); self.save(); return self.snapshot()

    def snapshot(self) -> dict[str, Any]:
        remaining = 0
        if self.state.get("active") and self.state.get("ends_at"):
            remaining = max(0, int(float(self.state["ends_at"]) - _now().timestamp()))
            if remaining <= 0:
                # Do not auto-write just because UI reads state; represent due completion.
                return {**self.state, "remaining_seconds": 0, "due": True}
        return {**self.state, "remaining_seconds": remaining, "due": False}
