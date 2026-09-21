from mary.distributed.computer_use_contract import (
    ComputerUseGrant,
    authorize_computer_use,
    make_computer_use_request,
)


def test_mutating_computer_use_requires_exact_request_scoped_grant():
    request = make_computer_use_request(
        node_id="DESKTOP-ATS5OPV", action="click", turn_id="turn-1", request_id="req-1"
    )
    assert authorize_computer_use(request, None) == (False, "request_scoped_grant_required")
    wrong = ComputerUseGrant("req-1", "turn-old", "DESKTOP-ATS5OPV", True)
    assert authorize_computer_use(request, wrong) == (False, "grant_scope_mismatch")
    exact = ComputerUseGrant("req-1", "turn-1", "DESKTOP-ATS5OPV", True)
    assert authorize_computer_use(request, exact) == (True, "request_scoped_grant_verified")


def test_observation_does_not_need_mutation_grant():
    request = make_computer_use_request(
        node_id="pc", action="observe_screen", turn_id="turn-2", request_id="req-2"
    )
    assert request.requires_grant is False
    assert authorize_computer_use(request, None) == (True, "read_only_observation")
