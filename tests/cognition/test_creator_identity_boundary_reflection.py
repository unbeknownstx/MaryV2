from __future__ import annotations

from mary.cognition.context import CognitiveContext
from mary.cognition.reasoning import ReasoningResult
from mary.cognition.reflection import ReflectionDecision, ReflectionEngine
from mary.llm.interface import LLMProviderError, LLMResponse


def _context(input_text: str) -> CognitiveContext:
    profile = {
        "facts": {"test_animal": "a red panda"},
        "preferences": {"favorite_color": "green"},
        "interests": ["creating stories"],
        "values": [],
        "goals": ["finish MaryV2"],
        "communication_style": {"preferred_style": "be direct and concise"},
    }
    return CognitiveContext(
        input_text=input_text,
        user_context={
            "creator_id": "creator",
            "name": "unbe",
            **profile,
        },
        mind_state={
            "identity": {
                "name": "Mary",
                "creator": "Unbe",
                "entity_type": "AI character",
            },
            "relationship": {
                "creator_name": "Unbe",
                "role": "creator",
                "current_profile": profile,
            },
            "disposition": {"mode": "relational_conversation"},
            "continuity": {"allow_follow_up_question": True, "drive": "answer"},
        },
    )


class RevisionLLM:
    def __init__(self, content: str) -> None:
        self.content = content
        self.calls = []

    def generate(self, messages, **kwargs):
        self.calls.append((messages, kwargs))
        return LLMResponse(
            content=self.content,
            provider="test",
            model="identity-boundary-test",
            finish_reason="stop",
            usage={},
        )


class FailingRevisionLLM:
    def __init__(self) -> None:
        self.calls = 0

    def generate(self, messages, **kwargs):
        self.calls += 1
        raise LLMProviderError("revision unavailable")


def test_creator_favorite_color_cannot_be_adopted_as_marys_own():
    engine = ReflectionEngine(llm=RevisionLLM("Green is your favorite color; I don't have one represented for myself."))
    context = _context("What is your favorite color?")

    issues = engine._character_audit(
        context=context,
        reasoning=ReasoningResult(response="Green. I love that soft garden kind of green."),
        intent=None,
    )

    assert any("Creator/self ownership boundary" in issue for issue in issues)
    assert any("preferences.favorite_color" in issue for issue in issues)


def test_creator_fact_can_be_mentioned_when_explicitly_attributed_to_unbe():
    engine = ReflectionEngine(llm=RevisionLLM("unused"))
    context = _context("What is my favorite color?")

    issues = engine._creator_ownership_audit(
        context=context,
        reasoning=ReasoningResult(
            response="Your favorite color is green. That's in my profile of you, not my own identity."
        ),
    )

    assert issues == []


def test_creator_interest_cannot_be_claimed_in_first_person():
    engine = ReflectionEngine(llm=RevisionLLM("unused"))
    context = _context("Tell me about yourself.")

    issues = engine._creator_ownership_audit(
        context=context,
        reasoning=ReasoningResult(response="I love creating stories."),
    )

    assert any("interests" in issue for issue in issues)


def test_creator_fact_cannot_be_folded_into_marys_self_description():
    engine = ReflectionEngine(llm=RevisionLLM("unused"))
    context = _context("Who are you?")

    issues = engine._creator_ownership_audit(
        context=context,
        reasoning=ReasoningResult(
            response="I'm Mary. I've got a name, a little story, and a red panda test animal."
        ),
    )

    assert any("facts.test_animal" in issue for issue in issues)


def test_self_grounded_response_still_reuses_without_second_call_when_boundary_is_clean():
    llm = RevisionLLM("unused")
    engine = ReflectionEngine(llm=llm)
    context = _context("Who are you?")

    result = engine.reflect(
        context=context,
        reasoning=ReasoningResult(
            response="I'm Mary, an AI character created by Unbe. Your profile is context about you, not my identity.",
            metadata={"self_grounded": True},
        ),
    )

    assert result.decision == ReflectionDecision.ACCEPT
    assert result.metadata["mode"] == "self_introspection_grounding_reuse"
    assert llm.calls == []


def test_self_grounded_creator_bleed_enters_existing_revision_path():
    llm = RevisionLLM(
        "I'm Mary. Green is your favorite color; I don't have a favorite color represented for myself."
    )
    engine = ReflectionEngine(llm=llm)
    context = _context("What is your favorite color?")

    result = engine.reflect(
        context=context,
        reasoning=ReasoningResult(
            response="Green. That's my favorite color.",
            metadata={"self_grounded": True},
        ),
    )

    assert result.decision == ReflectionDecision.REVISE
    assert result.revised_response == llm.content
    assert len(llm.calls) == 1
    revision_prompt = "\n".join(message.content for message in llm.calls[0][0])
    assert "IDENTITY BOUNDARY" in revision_prompt
    assert "describe Unbe, not Mary" in revision_prompt


def test_failed_revision_uses_local_identity_safe_fallback_instead_of_leaking_creator_fact():
    llm = FailingRevisionLLM()
    engine = ReflectionEngine(llm=llm)
    context = _context("What is your favorite color?")

    result = engine.reflect(
        context=context,
        reasoning=ReasoningResult(response="Green. That's my favorite color."),
    )

    assert result.decision == ReflectionDecision.REVISE
    assert result.metadata["mode"] == "creator_identity_boundary_fallback"
    assert "don't have a favorite color represented" in result.revised_response.lower()
    assert "belongs to you" in result.revised_response.lower()


def test_bad_model_revision_is_reaudited_and_replaced_by_local_boundary_fallback():
    llm = RevisionLLM("Green. Still mine.")
    engine = ReflectionEngine(llm=llm)
    context = _context("What is your favorite color?")

    result = engine.reflect(
        context=context,
        reasoning=ReasoningResult(response="Green. That's my favorite color."),
    )

    assert result.decision == ReflectionDecision.REVISE
    assert result.metadata["mode"] == "creator_identity_boundary_fallback"
    assert "don't have a favorite color represented" in result.revised_response.lower()
