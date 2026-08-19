from __future__ import annotations

from mary.core.mary import Mary
from mary.llm.interface import LLMResponse
from mary.runtime.application import create_application


class NaturalLearningFakeRouter:
    def __init__(self, responses: list[str] | None = None):
        self.responses = list(responses or [])
        self.calls = []

    def generate(self, messages, **kwargs):
        self.calls.append((messages, kwargs))
        content = self.responses.pop(0) if self.responses else "Got it."
        return LLMResponse(
            content=content,
            provider="test",
            model="natural-learning-fake",
            finish_reason="stop",
            usage={},
        )

    def provider_name(self, provider=None):
        return "test"

    def model_name(self, provider=None):
        return "natural-learning-fake"

    def is_available(self, provider=None):
        return True


def _wire_fake(mary: Mary, responses: list[str] | None = None) -> NaturalLearningFakeRouter:
    router = NaturalLearningFakeRouter(responses)
    mary.llm = router
    mary.reasoning.llm = router
    mary.reflection.llm = router
    mary.conversation.router = router
    return router


def _creator_profile(mary: Mary) -> dict:
    profile = mary.user_model.current_profile()
    return profile if isinstance(profile, dict) else {}


def test_direct_communication_preference_is_learned_without_magic_prefix(tmp_path, monkeypatch):
    monkeypatch.chdir(tmp_path)
    mary = Mary()
    _wire_fake(mary, ["Yep, quick updates works for me."])

    result = mary.process(
        "I prefer you to give me quick updates while you work."
    )

    meta = result.metadata["natural_relationship_learning"]
    assert meta["detected"] is True
    assert meta["learned"] is True
    assert meta["signal_type"] == "communication_preference"
    profile = _creator_profile(mary)
    assert "quick updates" in str(profile.get("communication_style", {})).lower()
    assert "quick updates" in mary.relationship.answer_query("overview").lower()


def test_natural_creator_preference_never_becomes_marys_preference(tmp_path, monkeypatch):
    monkeypatch.chdir(tmp_path)
    mary = Mary()
    _wire_fake(mary)

    mary.process("I like synthwave music.")

    # RelationshipManager remains authoritative for categorization. A natural
    # "I like ..." share may be represented as an interest rather than a keyed
    # preference, but it must remain creator-owned and visible in the overview.
    assert "synthwave" in mary.relationship.answer_query("overview").lower()
    assert mary.preferences.get_preference("synthwave music") is None


def test_natural_goal_uses_existing_structured_relationship_parser(tmp_path, monkeypatch):
    monkeypatch.chdir(tmp_path)
    mary = Mary()
    _wire_fake(mary)

    result = mary.process("My main goal is finish MaryV2.")

    meta = result.metadata["natural_relationship_learning"]
    assert meta["signal_type"] == "goal"
    assert meta["learned"] is True
    assert "finish maryv2" in mary.relationship.answer_query("goals").lower()


def test_questions_and_uncertain_statements_are_not_naturally_learned(tmp_path, monkeypatch):
    monkeypatch.chdir(tmp_path)
    mary = Mary()
    _wire_fake(mary, ["Maybe.", "Fair."])

    first = mary.process("Do I prefer quick updates?")
    second = mary.process("I might prefer quick updates.")

    assert "natural_relationship_learning" not in first.metadata
    assert "natural_relationship_learning" not in second.metadata
    assert "quick updates" not in mary.relationship.answer_query("preferences").lower()


def test_past_only_statement_is_not_promoted_to_current_creator_fact(tmp_path, monkeypatch):
    monkeypatch.chdir(tmp_path)
    mary = Mary()
    _wire_fake(mary)

    result = mary.process("I used to like country music.")

    assert "natural_relationship_learning" not in result.metadata
    assert "country music" not in mary.relationship.answer_query("preferences").lower()


def test_duplicate_natural_share_does_not_duplicate_durable_memory(tmp_path, monkeypatch):
    monkeypatch.chdir(tmp_path)
    mary = Mary()
    _wire_fake(mary, ["Got it.", "Still got it."])

    statement = "I prefer you to give me concise checkpoint updates."

    first = mary.process(statement)
    first_count = mary.memory.episodic.count()

    second = mary.process(statement)
    second_count = mary.memory.episodic.count()

    assert first.metadata["natural_relationship_learning"]["learned"] is True
    assert second.metadata["natural_relationship_learning"]["already_known"] is True
    assert second_count == first_count


def test_natural_relationship_fact_is_available_in_same_turn_context(tmp_path, monkeypatch):
    monkeypatch.chdir(tmp_path)
    mary = Mary()
    _wire_fake(mary)

    result = mary.process("I value honesty.")

    user_context = result.context.user_context
    rendered = str(user_context).lower()
    assert "honesty" in rendered
    assert result.metadata["natural_relationship_learning"]["learned"] is True


def test_natural_relationship_learning_survives_persistent_restart(tmp_path, monkeypatch):
    monkeypatch.chdir(tmp_path)
    memory_path = tmp_path / "memory" / "memory.json"
    developed_path = tmp_path / "personality" / "developed_self.json"
    promotion_path = tmp_path / "personality" / "preference_promotion.json"

    first = create_application(
        memory_path=memory_path,
        developed_self_path=developed_path,
        preference_promotion_path=promotion_path,
        auto_save=True,
    )
    _wire_fake(first.mary)
    first.mary.process("I'm interested in animation.")
    first.close()

    second = create_application(
        memory_path=memory_path,
        developed_self_path=developed_path,
        preference_promotion_path=promotion_path,
        auto_save=True,
    )

    assert "animation" in second.mary.relationship.answer_query("interests").lower()
    assert any(
        getattr(memory, "metadata", {}).get("event_type") == "creator_natural_share"
        for memory in second.mary.memory.episodic.all()
    )
    second.close()

def test_relationship_preview_is_pure_and_reports_semantic_duplicate(tmp_path, monkeypatch):
    monkeypatch.chdir(tmp_path)
    mary = Mary()

    before_records = len(mary.user_model.get_profile_records(current_only=False))
    preview = mary.relationship.preview_explicit(
        "I prefer you to give me quick updates while you work."
    )
    after_records = len(mary.user_model.get_profile_records(current_only=False))

    assert preview is not None
    assert preview["category"] == "communication"
    assert preview["already_known"] is False
    assert after_records == before_records

    committed = mary.relationship.learn_explicit(
        "I prefer you to give me quick updates while you work.",
        source="test",
        evidence_id="event_1",
    )
    duplicate = mary.relationship.preview_explicit(
        "I prefer you to give me quick updates while you work."
    )

    assert committed is not None
    assert committed.get("already_known") is not True
    assert duplicate is not None
    assert duplicate["already_known"] is True


def test_relationship_manager_accepts_direct_i_like_as_interest(tmp_path, monkeypatch):
    monkeypatch.chdir(tmp_path)
    mary = Mary()

    learned = mary.relationship.learn_explicit(
        "I like synthwave music.",
        source="test",
        evidence_id="event_synthwave",
    )

    assert learned is not None
    assert learned["category"] == "interest"
    assert "synthwave" in mary.relationship.answer_query("interests").lower()


def test_learn_explicit_semantically_deduplicates_new_evidence_ids(tmp_path, monkeypatch):
    monkeypatch.chdir(tmp_path)
    mary = Mary()

    first = mary.relationship.learn_explicit(
        "I value honesty.",
        source="test",
        evidence_id="event_1",
    )
    second = mary.relationship.learn_explicit(
        "I value honesty.",
        source="test",
        evidence_id="event_2",
    )

    assert first is not None
    assert second is not None
    assert second["already_known"] is True
    current_values = mary.user_model.get_profile_records(category="value")
    assert len(current_values) == 1

