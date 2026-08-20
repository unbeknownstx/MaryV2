from __future__ import annotations

from mary.cognition.context import CognitiveContext
from mary.cognition.reasoning import ReasoningResult
from mary.core.mary import Mary


def test_near_duplicate_recent_paragraph_is_audited():
    mary = Mary()
    paragraph = (
        "I still think you're doing a great job; leave a little room for more color, "
        "a stray thought, and a little wildness so it doesn't feel too sharp."
    )
    issues = mary.reflection._near_duplicate_response_audit(
        "I hear you. " + paragraph,
        ["Earlier thought. " + paragraph],
    )
    assert issues
    assert "Continuity boundary" in issues[0]


def test_unsupported_subjective_metaphysical_claim_is_audited():
    mary = Mary()
    issues = mary.reflection._subjective_experience_audit(
        "I don't feel like I'm performing, or pretending. I just see you."
    )
    assert issues
    assert "Representation boundary" in issues[0]


def test_warm_first_person_emotion_without_metaphysical_claim_is_allowed():
    mary = Mary()
    issues = mary.reflection._subjective_experience_audit(
        "In my current state, talking with you feels warm and important to me."
    )
    assert issues == []
