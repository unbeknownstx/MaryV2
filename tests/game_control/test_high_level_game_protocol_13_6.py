import pytest

from mary.distributed import CapabilityDescriptor, NodeDescriptor, NodeRegistry
from mary.game_control import (
    GameAction,
    GameActionRouter,
    GameActionValidationError,
)


def test_game_router_selects_capable_node_without_executing_low_level_controls():
    registry = NodeRegistry()
    registry.register(NodeDescriptor(
        node_id="game-pc",
        role="worker",
        host_type="desktop",
        platform="win32",
        capabilities={
            "game.control.high_level": CapabilityDescriptor(
                "game.control.high_level"
            )
        },
    ))
    routed = GameActionRouter(registry).route(
        GameAction("move_to", target="north door", game_id="demo")
    )
    assert routed["route"]["selected_node_id"] == "game-pc"
    assert routed["execution"] == "not_authorized"
    assert "high-level intent" in routed["policy"]


def test_game_protocol_rejects_raw_keypress_verbs():
    with pytest.raises(GameActionValidationError):
        GameAction("keypress_w")
