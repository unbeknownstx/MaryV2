"""High-level game action protocol.

Mary chooses semantic intent; replaceable adapters execute frame/button-level
control. This module validates and routes intent only and never emits raw
keyboard/mouse commands by itself.
"""
from __future__ import annotations

from dataclasses import asdict, dataclass, field
from typing import Any
import uuid


class GameActionValidationError(ValueError):
    pass


_ALLOWED = {
    "move_to",
    "follow",
    "interact",
    "inspect",
    "attack",
    "defend",
    "use_item",
    "equip",
    "open_menu",
    "choose_dialogue",
    "buy",
    "sell",
    "wait",
    "cancel",
}


@dataclass(frozen=True)
class GameAction:
    verb: str
    target: str = ""
    game_id: str = ""
    urgency: float = 0.5
    constraints: dict[str, Any] = field(default_factory=dict)
    action_id: str = field(
        default_factory=lambda: f"game_action_{uuid.uuid4().hex[:12]}"
    )

    def __post_init__(self) -> None:
        verb = str(self.verb or "").strip().lower()
        if verb not in _ALLOWED:
            raise GameActionValidationError(
                f"unsupported high-level game verb: {verb}"
            )
        object.__setattr__(self, "verb", verb)
        object.__setattr__(self, "target", str(self.target or "")[:240])
        object.__setattr__(self, "game_id", str(self.game_id or "")[:96])
        object.__setattr__(
            self,
            "urgency",
            max(0.0, min(1.0, float(self.urgency))),
        )
        clean_constraints = {
            str(key)[:64]: str(value)[:160]
            for key, value in list(dict(self.constraints or {}).items())[:12]
        }
        object.__setattr__(self, "constraints", clean_constraints)

    def to_dict(self) -> dict[str, Any]:
        return asdict(self)


class GameActionRouter:
    """Route semantic game intent without granting execution permission."""

    VERSION = "13.6"
    CAPABILITY = "game.control.high_level"

    def __init__(self, node_registry: Any) -> None:
        self.node_registry = node_registry

    def route(self, action: GameAction) -> dict[str, Any]:
        preview = self.node_registry.route_preview(self.CAPABILITY)
        return {
            "version": self.VERSION,
            "action": action.to_dict(),
            "route": preview,
            "execution": "not_authorized",
            "policy": (
                "Mary Core chooses high-level intent; a bounded capability adapter "
                "owns low-level game control and local permission"
            ),
        }
