"""
MaryV2 - Mary Core Integration Tests

Tests the top-level Mary coordinator and verifies that
its major subsystems work together through Mary's public API.
"""

from mary.core.mary import Mary


def test_mary_initializes():
    mary = Mary()

    assert mary.identity is not None
    assert mary.personality is not None
    assert mary.personality_development is not None
    assert mary.user_model is not None
    assert mary.learner is not None
    assert mary.memory is not None


def test_mary_status():
    mary = Mary()

    status = mary.status()

    assert isinstance(status, dict)

    assert status["name"] == "Mary"
    assert "identity" in status
    assert "personality" in status
    assert "personality_development" in status
    assert "user" in status
    assert "learning" in status
    assert "memory" in status


def test_mary_describe_self():
    mary = Mary()

    description = mary.describe_self()

    assert isinstance(description, str)
    assert "Mary" in description


def test_mary_describe_user():
    mary = Mary()

    user = mary.describe_user()

    assert isinstance(user, dict)
    assert user["name"] == "unbe"


def test_mary_can_learn():
    mary = Mary()

    event = mary.learn(
        event_type="experience",
        subject="testing",
        content="Mary successfully completed an integration test.",
        confidence=0.9,
        usefulness=0.8,
    )

    assert event is not None
    assert event.event_type == "experience"
    assert event.subject == "testing"
    assert event.content == (
        "Mary successfully completed an integration test."
    )
    assert event.confidence == 0.9
    assert event.usefulness == 0.8

    summary = mary.learner.summarize()

    assert summary["total_events"] == 1


def test_mary_can_remember():
    mary = Mary()

    result = mary.remember(
        "Mary's core integration test was successful.",
    )

    # The MemoryManager currently has no storage subsystem
    # connected, so returning None is expected at this stage.
    assert result is None


def test_mary_can_propose_personality_change():
    mary = Mary()

    proposal = mary.propose_personality_change(
        trait="curiosity",
        amount=0.05,
        reason="Mary encountered something interesting.",
        confidence=0.9,
    )

    assert proposal["trait"] == "curiosity"
    assert proposal["requested_change"] == 0.05
    assert proposal["confidence"] == 0.9
    assert proposal["status"] == "pending"

    pending = (
        mary.personality_development.get_pending()
    )

    assert len(pending) == 1


def test_mary_can_apply_personality_change():
    mary = Mary()

    original = mary.personality.get_trait(
        "curiosity"
    )

    proposal = mary.propose_personality_change(
        trait="curiosity",
        amount=0.05,
        reason="Mary encountered something interesting.",
        confidence=0.9,
    )

    applied = mary.apply_personality_change(
        proposal
    )

    assert applied is True

    updated = mary.personality.get_trait(
        "curiosity"
    )

    assert updated == 0.85
    assert updated > original


def test_mary_can_reject_personality_change():
    mary = Mary()

    proposal = mary.propose_personality_change(
        trait="curiosity",
        amount=0.05,
        reason="Testing rejection.",
        confidence=0.9,
    )

    rejected = mary.reject_personality_change(
        proposal,
        reason="Test rejection.",
    )

    assert rejected is True

    assert (
        mary.personality_development.get_pending()
        == []
    )

    history = (
        mary.personality_development.get_history()
    )

    assert len(history) == 1
    assert history[0]["status"] == "rejected"