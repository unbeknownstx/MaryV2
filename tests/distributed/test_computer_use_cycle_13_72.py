from mary.distributed.computer_use_contract import ComputerUseGrant, make_computer_use_request
from mary.distributed.computer_use_cycle import plan_computer_use_cycle


def test_cycle_uses_real_observation_lane_around_typed_mutation():
    request = make_computer_use_request(node_id="pc", action="click", turn_id="t", request_id="r")
    grant = ComputerUseGrant("r", "t", "pc", True)
    cycle = plan_computer_use_cycle(
        request, grant=grant, action_capability="mcp.desktop_control",
        action_args={"target": "approved"},
    )
    assert cycle.observe.capability == "sensor.screen_describe"
    assert cycle.action.capability == "mcp.desktop_control"
    assert cycle.verify.capability == "sensor.screen_describe"
    assert cycle.observe.args["computer_use_request_id"] == "r:observe"
    assert cycle.verify.args["computer_use_request_id"] == "r:verify"
