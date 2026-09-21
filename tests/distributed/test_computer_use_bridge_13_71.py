import pytest

from mary.distributed.computer_use_bridge import bridge_computer_use
from mary.distributed.computer_use_contract import (
    ComputerUseGrant,
    make_computer_use_request,
)


def test_read_only_screen_observation_maps_to_existing_sensor_lane():
    request = make_computer_use_request(node_id="pc", action="observe_screen", turn_id="t", request_id="r")
    dispatch = bridge_computer_use(request)
    assert dispatch.capability == "sensor.screen_describe"\n    assert dispatch.args["mode"] == "ui"
    assert dispatch.mutating is False


def test_mutation_needs_grant_and_explicit_typed_adapter():
    request = make_computer_use_request(node_id="pc", action="click", turn_id="t", request_id="r")
    grant = ComputerUseGrant("r", "t", "pc", True)
    with pytest.raises(ValueError):
        bridge_computer_use(request, grant=grant)
    dispatch = bridge_computer_use(
        request, grant=grant, action_capability="mcp.desktop_control",
        action_args={"target": "approved-adapter"},
    )
    assert dispatch.mutating is True
    assert dispatch.args["verify_after"] is True
