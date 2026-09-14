from mary.distributed.execution_reliability import (
    ExecutionBudget,
    ExecutionEvidence,
    ProgressGuard,
    ReliabilityLedger,
    derive_side_effect_key,
    should_retry,
    stable_args_fingerprint,
)


def test_argument_fingerprint_retains_no_prompt_text():
    args = {"messages": [{"role": "user", "content": "private creator text"}], "max_tokens": 20}
    fingerprint = stable_args_fingerprint(args)
    assert len(fingerprint) == 20
    assert "private" not in fingerprint


def test_retry_policy_never_replays_mutation_or_cancelled_work():
    budget = ExecutionBudget(max_attempts=3)
    assert should_retry(attempt=1, budget=budget, error="connection refused", mutating=False)
    assert not should_retry(attempt=1, budget=budget, error="connection refused", mutating=True)
    assert not should_retry(attempt=1, budget=budget, error="timeout", mutating=False, cancelled=True)
    assert not should_retry(attempt=3, budget=budget, error="timeout", mutating=False)


def test_progress_guard_steers_then_halts_repeated_identical_reads():
    guard = ProgressGuard(steer_repeat=3, halt_repeat=5)
    verdicts = [guard.before("personal_search", {"query": "same"}) for _ in range(5)]
    assert verdicts[2].action == "steer"
    assert verdicts[-1].action == "halt"


def test_successful_mutation_starts_a_new_progress_epoch():
    guard = ProgressGuard(steer_repeat=3, halt_repeat=5)
    guard.before("personal_search", {"query": "same"})
    guard.before("personal_search", {"query": "same"})
    guard.after(success=True, mutating=True)
    assert guard.before("personal_search", {"query": "same"}).action == "ok"


def test_side_effect_keys_serialize_shared_inference_and_mcp_resources():
    assert derive_side_effect_key("llm.ollama", {}) == "inference:llm.ollama"
    assert derive_side_effect_key("mcp.scrapling", {"tool": "fetch"}) == "mcp:scrapling:fetch"
    assert derive_side_effect_key("personal_search", {}) is None


def test_reliability_ledger_is_content_free_and_non_authoritative():
    ledger = ReliabilityLedger()
    ledger.record(ExecutionEvidence(
        capability="llm.ollama",
        operation="conversation",
        success=True,
        elapsed_ms=123.0,
        output_units=18,
    ))
    snapshot = ledger.snapshot()
    assert snapshot["authority"] == "operational_hint_only"
    assert snapshot["content_retained"] is False
    assert ledger.success_rate("llm.ollama", "conversation") == 1.0
