from mary.distributed import CapabilityInvocationLedger, CapabilitySimulator


def test_idempotency_returns_existing_invocation_and_retries_only_transient():
    ledger = CapabilityInvocationLedger()
    first, created = ledger.begin(
        "game.control.high_level",
        args={"verb": "move_to", "target": "door"},
    )
    assert created is True
    same, created_again = ledger.begin(
        "game.control.high_level",
        args={"target": "door", "verb": "move_to"},
    )
    assert created_again is False
    assert same.invocation_id == first.invocation_id
    ledger.start_attempt(first.idempotency_key)
    assert ledger.fail(first.idempotency_key, "timeout") is True
    ledger.start_attempt(first.idempotency_key)
    assert ledger.fail(first.idempotency_key, "permission_denied") is False


def test_capability_simulator_is_a_fake_adapter_not_mary_state():
    sim = CapabilitySimulator()
    sim.register(
        "game.control.high_level",
        lambda args: {"accepted": args["verb"]},
    )
    result = sim.invoke("game.control.high_level", {"verb": "inspect"})
    assert result.ok is True
    assert result.result["accepted"] == "inspect"
    assert "never canonical Mary" in sim.status()["policy"]
