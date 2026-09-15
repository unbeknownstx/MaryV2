from mary.relationship.natural_learning import NaturalRelationshipLearner


def test_natural_learning_accepts_parser_aligned_generic_creator_fact():
    learner = NaturalRelationshipLearner()
    candidate = learner.detect("My work schedule is 12 to 8:30")
    assert candidate is not None
    assert candidate["signal_type"] == "fact"


def test_natural_learning_accepts_parser_aligned_communication_preferences():
    learner = NaturalRelationshipLearner()
    assert learner.detect("I prefer you to keep replies concise")["signal_type"] == "communication_preference"
    assert learner.detect("I prefer when you talk naturally")["signal_type"] == "communication_preference"


def test_natural_learning_does_not_claim_unsupported_communication_phrase():
    learner = NaturalRelationshipLearner()
    assert learner.detect("I like it when you keep replies concise") is None


def test_natural_learning_still_rejects_questions_and_uncertainty():
    learner = NaturalRelationshipLearner()
    assert learner.detect("What is my work schedule?") is None
    assert learner.detect("Maybe my work schedule is noon to eight") is None
