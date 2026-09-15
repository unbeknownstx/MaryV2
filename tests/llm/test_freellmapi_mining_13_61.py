from mary.llm.context_fidelity import check_projection_fidelity
from mary.llm.request_guardrails import apply_request_budget, reserve_output_tokens
from mary.llm.session_affinity import SessionAffinityBook


def test_output_reservation_is_bounded():
    assert reserve_output_tokens(999999) == 2000


def test_budget_caps_output_without_retaining_content():
    result = apply_request_budget(estimated_input_tokens=900, requested_max_tokens=500, total_budget=1000)
    assert result.accepted is True
    assert result.effective_max_tokens == 100
    assert result.public_dict()["content_retained"] is False


def test_budget_rejects_input_overflow():
    result = apply_request_budget(estimated_input_tokens=1001, requested_max_tokens=50, total_budget=1000)
    assert result.accepted is False
    assert result.reason == "input_budget_exhausted"


def test_fidelity_rejects_lost_creator_constraint_and_number():
    before = 'You must keep port 3001.\n{"limit": 47}\n@@ -1 +1 @@\nbody'
    after = '{"limit": 47}\n@@ -1 +1 @@\nbody'
    assert check_projection_fidelity(before, after).accepted is False


def test_fidelity_accepts_compaction_that_preserves_critical_literals():
    before = 'noise noise noise noise noise\nYou must keep port 3001.\n{"limit": 47}\n@@ -1 +1 @@'
    after = 'You must keep port 3001.\n{"limit": 47}\n@@ -1 +1 @@'
    assert check_projection_fidelity(before, after).accepted is True


def test_session_affinity_is_bounded_ephemeral_and_content_free():
    book = SessionAffinityBook(ttl_seconds=30, max_sessions=8)
    book.set("creator-primary", "groq/model-a", now=10)
    assert book.get("creator-primary", now=20) == "groq/model-a"
    assert book.get("creator-primary", now=41) is None
    assert book.snapshot()["content_retained"] is False
