from mary.memory.action_policy import MemoryActionPolicy
from mary.memory.manager import MemoryManager


def test_changed_structured_fact_becomes_temporal_candidate_not_direct_write():
    decision = MemoryActionPolicy().decide(
        content="Creator now prefers CLI workflows.",
        structured_fact=True,
        changed_fact=True,
        confidence=0.95,
    )
    assert decision.action == "temporal_update_candidate"
    assert decision.persistence == "candidate_only"
    assert decision.requires_review is True


def test_relationship_owned_evidence_delegates_to_relationship_owner():
    decision = MemoryActionPolicy().decide(
        content="We completed a shared milestone.",
        relationship_owned=True,
        importance=0.95,
    )
    assert decision.action == "relationship_owner"
    assert decision.persistence == "delegate"


def test_low_value_evidence_is_not_persisted_and_manager_exposes_policy():
    policy = MemoryActionPolicy()
    decision = policy.decide(content="transient cursor movement", importance=0.1)
    assert decision.action == "ignore"
    memory = MemoryManager()
    proposed = memory.propose_action(
        content="temporary scratch state",
        temporary=True,
    )
    assert proposed.action == "working"
    assert memory.status()["action_policy"]["mutates_memory"] is False
