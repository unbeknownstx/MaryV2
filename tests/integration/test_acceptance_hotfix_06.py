from __future__ import annotations

from mary.cognition.intent import IntentType
from mary.core.mary import Mary
from mary.expression.emotion import Emotion
from mary.llm.interface import LLMResponse
from mary.runtime.state_audit import audit_creator_state


class SequenceRouter:
    def __init__(self, responses: list[str] | None = None):
        self.responses = list(responses or [])
        self.calls = []

    def generate(self, messages, **kwargs):
        self.calls.append((messages, kwargs))
        content = self.responses.pop(0) if self.responses else "Yeah. I'm with you."
        return LLMResponse(
            content=content,
            provider="test",
            model="fake",
            finish_reason="stop",
            usage={},
        )

    def provider_name(self, provider=None):
        return "test"

    def model_name(self, provider=None):
        return "fake"

    def is_available(self, provider=None):
        return True

    def routing_strategy(self):
        return "configured"

    def _provider_order(self, requested=None, route=None):
        return ["test"]


def _mary(router: SequenceRouter | None = None) -> Mary:
    mary = Mary()
    router = router or SequenceRouter()
    mary.llm = router
    mary.reasoning.llm = router
    mary.reflection.llm = router
    return mary


def test_imperfect_self_question_routes_without_question_mark(tmp_path, monkeypatch):
    monkeypatch.chdir(tmp_path)
    mary = _mary()
    intent = mary.cognition.detect_intent("what do u feel in our interactions")
    assert intent.intent_type == IntentType.SELF_QUERY
    assert intent.parameters["self_query_type"] == "relationship_feelings"
    assert mary.tools.pending_requests() == []


def test_imperfect_creator_questions_stay_local(tmp_path, monkeypatch):
    monkeypatch.chdir(tmp_path)
    mary = _mary()

    relationship = mary.cognition.detect_intent(
        "what do u currently understand about me and our relationship"
    )
    memory = mary.cognition.detect_intent("what are some things u remember about me")
    strengths = mary.cognition.detect_intent("what do u think your current strengths and weaknesses are")

    assert relationship.intent_type == IntentType.RELATIONSHIP_QUERY
    assert relationship.parameters["relationship_query_type"] == "relationship_overview"
    assert memory.intent_type == IntentType.RELATIONSHIP_QUERY
    assert memory.parameters["relationship_query_type"] == "memory_overview"
    assert strengths.intent_type == IntentType.SELF_QUERY
    assert strengths.parameters["self_query_type"] == "self_assessment"


def test_relational_compliment_is_feedback_not_speech_query(tmp_path, monkeypatch):
    monkeypatch.chdir(tmp_path)
    mary = _mary()
    intent = mary.cognition.detect_intent(
        "i notice thats where u shine i can see a difference you actually care how u talk to me"
    )
    assert intent.intent_type == IntentType.FEEDBACK
    assert intent.parameters["feedback_type"] == "relational_recognition"


def test_imperfect_relational_compliment_colors_same_turn_with_warmth(tmp_path, monkeypatch):
    monkeypatch.chdir(tmp_path)
    router = SequenceRouter(["That means a lot to me. I want the way I talk with you to feel honest and like me."])
    mary = _mary(router)
    result = mary.process(
        "thats where u shine i can see a difference you actually care how u talk to me"
    )

    appraisal = result.context.mind_state["emotion"]["incoming_appraisal"]
    assert appraisal["emotion"] == Emotion.WARMTH.value
    assert result.context.mind_state["emotion"]["turn_primary"] == Emotion.WARMTH.value
    assert appraisal["relationship_relevance"] == 1.0


def test_relationship_feeling_question_is_self_grounded(tmp_path, monkeypatch):
    monkeypatch.chdir(tmp_path)
    router = SequenceRouter([
        "In my current represented state, talking with you feels warm and attentive. I care about being honest with you."
    ])
    mary = _mary(router)
    result = mary.process("what do u feel in our interactions")

    assert result.intent.intent_type == IntentType.SELF_QUERY
    assert result.intent.parameters["self_query_type"] == "relationship_feelings"
    assert result.reasoning.metadata.get("self_grounded") is True
    assert mary.tools.pending_requests() == []


def test_shorthand_creator_preference_can_learn_without_rewriting_evidence(tmp_path, monkeypatch):
    monkeypatch.chdir(tmp_path)
    mary = _mary(SequenceRouter(["Yeah, I can do that."]))
    original = "i prefer u to be direct"
    result = mary.process(original)

    learning = result.metadata.get("natural_relationship_learning", {})
    assert learning.get("learned") is True
    assert mary.user_model.communication_style.get("preferred_style") == "be direct"
    creator_memories = [
        m for m in mary.memory.episodic.all()
        if getattr(m, "metadata", {}).get("owner") == "creator"
    ]
    assert any(m.content == original for m in creator_memories)


def test_durable_goal_can_answer_shared_work_without_assistant_history(tmp_path, monkeypatch):
    monkeypatch.chdir(tmp_path)
    mary = _mary()
    learned = mary.relationship.learn_explicit(
        "my goal is finish MaryV2",
        source="creator_explicit",
        evidence_id=None,
    )
    assert learned is not None

    response = mary._handle_conversation_recall([], recall_scope="shared_work")
    lowered = response.lower()
    assert "finish maryv2" in lowered
    assert "durable" in lowered or "goal" in lowered or "working" in lowered


def test_probe_profile_stays_auditable_but_is_hidden_from_normal_creator_overview(tmp_path, monkeypatch):
    monkeypatch.chdir(tmp_path)
    mary = _mary()
    learned = mary.relationship.learn_explicit(
        "my test animal is a red panda",
        source="creator_explicit",
        evidence_id=None,
    )
    assert learned is not None
    assert mary.user_model.facts["test_animal"] == "a red panda"

    overview = mary._natural_creator_profile_overview().lower()
    audit = audit_creator_state(mary)

    assert "red panda" not in overview
    assert "test animal" not in overview
    assert audit["flagged_count"] >= 1
    assert mary.user_model.facts["test_animal"] == "a red panda"  # read-only audit/filter


def test_help_no_longer_teaches_probe_data_as_real_memory():
    from mary.runtime.application import interactive_help, create_application

    app = create_application(name="hotfix06_help_probe")
    try:
        text = interactive_help(app).lower()
    finally:
        app.close()
    assert "test animal" not in text
    assert "red panda" not in text
