"""Dynamic, race-safe action windows for games and embodied worlds.

Inspired by the public Neuro SDK's register/unregister action contract, but
adapted to Mary's capability architecture.  A world/game publishes only the
actions that are valid *right now*.  Mary may select one, but execution remains
outside this registry and must still pass the existing capability/tool
permission boundary.

This registry does not execute code, own autonomy, or grant permissions.
"""
from __future__ import annotations

from dataclasses import asdict, dataclass, field
from datetime import datetime, timezone
from threading import RLock
from typing import Any, Mapping
import uuid

from mary.runtime.turn_observability import record_turn_stage
from mary.realtime.decision_trace import RealtimeDecisionTrace


def _now() -> str:
    return datetime.now(timezone.utc).isoformat()


def _clip(value: Any, limit: int) -> str:
    return " ".join(str(value or "").split())[:limit]


@dataclass(frozen=True)
class ActionSpec:
    name: str
    description: str
    schema: dict[str, Any] = field(default_factory=lambda: {"type": "object", "properties": {}})
    disposable: bool = False
    capability: str = ""
    metadata: dict[str, Any] = field(default_factory=dict)

    def validate_contract(self) -> None:
        name = _clip(self.name, 80)
        if not name or not all(ch.islower() or ch.isdigit() or ch in "_-" for ch in name):
            raise ValueError("Action names must be lowercase identifiers using letters, digits, _ or -.")
        if not _clip(self.description, 500):
            raise ValueError("Action descriptions are required.")
        schema = dict(self.schema or {})
        if schema.get("type", "object") != "object":
            raise ValueError("Action schemas must describe a JSON object.")
        if "properties" in schema and not isinstance(schema.get("properties"), dict):
            raise ValueError("Action schema properties must be an object.")

    def to_dict(self) -> dict[str, Any]:
        self.validate_contract()
        return {
            "name": self.name,
            "description": _clip(self.description, 500),
            "schema": dict(self.schema or {}),
            "disposable": bool(self.disposable),
            "capability": _clip(self.capability, 120),
            "metadata": {str(k)[:50]: str(v)[:140] for k, v in list(dict(self.metadata or {}).items())[:10]},
        }


@dataclass
class ActionWindow:
    window_id: str
    surface: str
    context: str
    actions: dict[str, ActionSpec]
    revision: int = 1
    created_at: str = field(default_factory=_now)
    updated_at: str = field(default_factory=_now)
    consumed_action_ids: set[str] = field(default_factory=set, repr=False)

    def to_dict(self) -> dict[str, Any]:
        return {
            "window_id": self.window_id,
            "surface": self.surface,
            "context": self.context,
            "revision": self.revision,
            "created_at": self.created_at,
            "updated_at": self.updated_at,
            "actions": [item.to_dict() for item in self.actions.values()],
        }


@dataclass(frozen=True)
class ActionSelection:
    selection_id: str
    window_id: str
    revision: int
    action: str
    args: dict[str, Any]
    capability: str
    disposable: bool
    status: str = "selected_not_executed"

    def to_dict(self) -> dict[str, Any]:
        return asdict(self)


class ActionWindowRegistry:
    """Current valid high-level actions, with idempotent disposable selection."""

    VERSION = "1"

    def __init__(self, *, max_windows: int = 24, decision_trace: RealtimeDecisionTrace | None = None) -> None:
        self.max_windows = max(2, min(128, int(max_windows)))
        self.decision_trace = decision_trace
        self._windows: dict[str, ActionWindow] = {}
        self._order: list[str] = []
        self._lock = RLock()

    def open(
        self,
        *,
        surface: str,
        context: str,
        actions: list[ActionSpec] | tuple[ActionSpec, ...],
        window_id: str | None = None,
    ) -> ActionWindow:
        action_map: dict[str, ActionSpec] = {}
        for action in actions:
            action.validate_contract()
            if action.name in action_map:
                raise ValueError(f"duplicate action name: {action.name}")
            action_map[action.name] = action
        if not action_map:
            raise ValueError("Action windows require at least one action.")
        target = _clip(window_id or f"action_window_{uuid.uuid4().hex[:12]}", 120)
        with self._lock:
            existing = self._windows.get(target)
            revision = 1 if existing is None else existing.revision + 1
            window = ActionWindow(
                window_id=target,
                surface=_clip(surface or "unknown", 80),
                context=_clip(context, 600),
                actions=action_map,
                revision=revision,
                created_at=existing.created_at if existing is not None else _now(),
                updated_at=_now(),
            )
            self._windows[target] = window
            if target not in self._order:
                self._order.append(target)
            while len(self._order) > self.max_windows:
                old = self._order.pop(0)
                self._windows.pop(old, None)
            record_turn_stage(
                "action_window", status="success", elapsed_ms=0.0, outcome="opened",
                result_ids={"action_window_id": window.window_id},
            )
            if self.decision_trace is not None:
                self.decision_trace.record(
                    "action_window", "opened", "current valid world/game actions changed",
                    source=window.surface, target="mary",
                    metadata={"window_id": window.window_id, "action_count": len(window.actions), "revision": window.revision},
                )
            return window

    def close(self, window_id: str) -> bool:
        target = str(window_id or "")
        with self._lock:
            removed = self._windows.pop(target, None) is not None
            if target in self._order:
                self._order.remove(target)
            return removed

    def get(self, window_id: str) -> ActionWindow | None:
        with self._lock:
            return self._windows.get(str(window_id or ""))

    @staticmethod
    def _validate_args(schema: Mapping[str, Any], args: Mapping[str, Any]) -> dict[str, Any]:
        # Deliberately small JSON-schema subset. The executing capability must
        # still do domain validation before touching the environment.
        values = dict(args or {})
        properties = dict(schema.get("properties") or {})
        required = {str(item) for item in list(schema.get("required") or [])}
        missing = sorted(item for item in required if item not in values)
        if missing:
            raise ValueError(f"missing required action arguments: {', '.join(missing)}")
        additional = schema.get("additionalProperties", True)
        if additional is False:
            unknown = sorted(key for key in values if key not in properties)
            if unknown:
                raise ValueError(f"unknown action arguments: {', '.join(unknown)}")
        safe: dict[str, Any] = {}
        for key, value in list(values.items())[:32]:
            spec = properties.get(key, {}) if isinstance(properties.get(key), dict) else {}
            expected = spec.get("type")
            if expected == "string":
                value = _clip(value, int(spec.get("maxLength", 1000) or 1000))
            elif expected == "integer":
                if isinstance(value, bool):
                    raise ValueError(f"{key} must be an integer")
                value = int(value)
            elif expected == "number":
                if isinstance(value, bool):
                    raise ValueError(f"{key} must be numeric")
                value = float(value)
            elif expected == "boolean":
                if not isinstance(value, bool):
                    raise ValueError(f"{key} must be boolean")
            safe[str(key)[:80]] = value
        return safe

    def select(
        self,
        *,
        window_id: str,
        action: str,
        args: Mapping[str, Any] | None = None,
        expected_revision: int | None = None,
        selection_id: str | None = None,
    ) -> ActionSelection:
        """Select one currently valid action without executing it.

        Disposable actions are removed atomically *before* the selection is
        returned, which prevents a second concurrent selection from racing the
        first action's result.
        """

        target = str(window_id or "")
        action_name = str(action or "").strip().lower()
        opaque = _clip(selection_id or f"action_selection_{uuid.uuid4().hex[:16]}", 120)
        with self._lock:
            window = self._windows.get(target)
            if window is None:
                raise LookupError("action window is no longer active")
            if expected_revision is not None and int(expected_revision) != window.revision:
                raise RuntimeError("action window revision changed; refresh valid actions")
            if opaque in window.consumed_action_ids:
                raise RuntimeError("duplicate action selection")
            spec = window.actions.get(action_name)
            if spec is None:
                raise LookupError("action is not valid in the current window")
            safe_args = self._validate_args(spec.schema, dict(args or {}))
            if spec.disposable:
                # Remove before result/dispatch to prevent racey double use.
                window.actions.pop(action_name, None)
                window.revision += 1
                window.updated_at = _now()
            window.consumed_action_ids.add(opaque)
            selection = ActionSelection(
                selection_id=opaque,
                window_id=target,
                revision=window.revision,
                action=spec.name,
                args=safe_args,
                capability=spec.capability,
                disposable=bool(spec.disposable),
            )
            record_turn_stage(
                "action_window", status="success", elapsed_ms=0.0, outcome="selected",
                result_ids={"action_window_id": target, "action_selection_id": opaque},
            )
            if self.decision_trace is not None:
                self.decision_trace.record(
                    "action_window", "selected", "Mary selected a currently valid high-level action; execution remains unauthorized",
                    source=window.surface, target=spec.capability or "capability",
                    metadata={"window_id": target, "action": spec.name, "disposable": bool(spec.disposable)},
                )
            return selection

    def snapshot(self) -> dict[str, Any]:
        with self._lock:
            windows = [self._windows[item].to_dict() for item in self._order if item in self._windows]
        return {
            "version": self.VERSION,
            "windows": windows,
            "policy": "dynamic valid-action catalog only; selection never bypasses Mary's tool/capability execution authorization",
        }
