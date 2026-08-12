import pytest

from mary.personality.personality import Personality
from mary.personality.development import PersonalityDevelopment


def test_personality_initialization():
    personality = Personality()

    assert personality.get_trait("curiosity") == pytest.approx(0.80)
    assert personality.get_trait("creativity") == pytest.approx(0.80)
    assert personality.get_trait("empathy") == pytest.approx(0.80)


def test_personality_trait_adjustment():
    personality = Personality()

    result = personality.adjust_trait(
        "curiosity",
        0.05,
    )

    assert result == pytest.approx(0.85)
    assert personality.get_trait("curiosity") == pytest.approx(0.85)


def test_personality_trait_bounds():
    personality = Personality()

    personality.adjust_trait(
        "curiosity",
        10.0,
    )

    assert personality.get_trait("curiosity") == pytest.approx(1.0)

    personality.adjust_trait(
        "curiosity",
        -10.0,
    )

    assert personality.get_trait("curiosity") == pytest.approx(0.0)


def test_personality_development_proposal():
    personality = Personality()

    development = PersonalityDevelopment(
        personality=personality,
    )

    proposal = development.propose_change(
        trait="curiosity",
        change=0.05,
        reason="Mary encountered something interesting.",
        confidence=0.9,
    )

    assert proposal["trait"] == "curiosity"
    assert proposal["requested_change"] == pytest.approx(0.05)
    assert proposal["confidence"] == pytest.approx(0.9)
    assert proposal["status"] == "pending"

    assert len(development.get_pending()) == 1


def test_personality_development_apply():
    personality = Personality()

    development = PersonalityDevelopment(
        personality=personality,
    )

    proposal = development.propose_change(
        trait="curiosity",
        change=0.05,
        reason="Mary encountered something interesting.",
        confidence=0.9,
    )

    assert personality.get_trait("curiosity") == pytest.approx(0.80)

    applied = development.apply(proposal)

    assert applied is True
    assert personality.get_trait("curiosity") == pytest.approx(0.85)

    assert len(development.get_history()) == 1
    assert len(development.get_pending()) == 0


def test_personality_development_reject():
    personality = Personality()

    development = PersonalityDevelopment(
        personality=personality,
    )

    proposal = development.propose_change(
        trait="curiosity",
        change=0.05,
        reason="Test rejection.",
        confidence=0.9,
    )

    rejected = development.reject(
        proposal,
        reason="Not enough evidence.",
    )

    assert rejected is True
    assert personality.get_trait("curiosity") == pytest.approx(0.80)

    assert len(development.get_pending()) == 0
    assert len(development.get_history()) == 1

    history = development.get_history()

    assert history[0]["status"] == "rejected"
    assert history[0]["reason"] == "Not enough evidence."


def test_personality_development_low_confidence():
    personality = Personality()

    development = PersonalityDevelopment(
        personality=personality,
    )

    proposal = development.propose_change(
        trait="curiosity",
        change=0.05,
        reason="Weak evidence.",
        confidence=0.2,
    )

    evaluation = development.evaluate(proposal)

    assert evaluation["approved"] is False
    assert evaluation["change"] == pytest.approx(0.0)

    applied = development.apply(proposal)

    assert applied is False
    assert personality.get_trait("curiosity") == pytest.approx(0.80)