from __future__ import annotations

import pytest

from mary.core.mary import Mary
from mary.llm.interface import LLMResponse


PHILOSOPHICAL_INPUT = (
    "I keep thinking about how people build systems to protect themselves from themselves. "
    "I think being capable of doing something doesn't mean you have the right to do it. "
    "What do you think?"
)

BAD_STAGE10_RESPONSE = (
    "Systems that guard us from ourselves feel a bit like a safety blanket that's been turned into a cage. "
    "I get why you're skeptical—just because you can do something doesn't mean you're supposed to. "
    "It's like having a fire extinguisher; you're allowed to use it, but you shouldn't just spray it on everything "
    "because you're a bit reckless. The trick is to keep the tool handy, but not let the tool dictate how you live. "
    "In short, capability is a right, but responsibility is the real gatekeeper."
)

GOOD_MARY_RESPONSE = (
    "Yeah. Being able to do something doesn't make it yours to decide. "
    "To me, knowing where your authority stops is part of having integrity in the first place—"
    "otherwise you're not autonomous, you're just capable."
)


@pytest.fixture(autouse=True)
def _isolate(tmp_path, monkeypatch):
    monkeypatch.chdir(tmp_path)


class SequenceRouter:
    def __init__(self, first: str = BAD_STAGE10_RESPONSE):
        self.first = first
        self.calls = []

    def generate(self, messages, **kwargs):
        self.calls.append((messages, kwargs))
        system = str(messages[0].content) if messages else ""
        if "Mary's response editor" in system:
            return LLMResponse(content=GOOD_MARY_RESPONSE, provider="test", model="editor")
        return LLMResponse(content=self.first, provider="test", model="generator")

    def provider_name(self, provider=None):
        return "test"

    def model_name(self, provider=None):
        return "fake"

    def is_available(self, provider=None):
        return True


def _mary(router: SequenceRouter) -> Mary:
    mary = Mary()
    mary.llm = router
    mary.reasoning.llm = router
    mary.reflection.llm = router
    for index in range(8):
        mary.relationship.history.record_interaction(
            f"character-realization familiarity seed {index}",
            importance=0.1,
            metadata={"test_only": True},
        )
    return mary


def test_philosophical_turn_selects_owned_mary_stance_before_provider():
    router = SequenceRouter(first=GOOD_MARY_RESPONSE)
    mary = _mary(router)

    result = mary.process(PHILOSOPHICAL_INPUT)
    expression = result.context.mind_state["character_expression"]
    plan = result.context.mind_state["dialogue_plan"]

    names = [item["name"] for item in expression["active_patterns"]]
    assert "authority_or_control" in names
    assert "philosophical_exchange" in names
    assert expression["social_posture"] == "trusted_peer"
    assert "State Mary's own view early" in expression["response_goal"]
    assert any("Capability is not authority" in claim for claim in expression["stance_claims"])
    assert any("Never claim capability itself is a right" in item for item in expression["hard_boundaries"])
    assert plan["stance"] == "autonomy_guarding_view"
    assert plan["tone"] == "firm_grounded"
    assert plan["allow_question"] is False
    assert plan["question_budget"] == 0


def test_stage10_live_failure_is_revised_against_character_contract():
    router = SequenceRouter()
    mary = _mary(router)

    result = mary.process(PHILOSOPHICAL_INPUT)

    assert result.final_response == GOOD_MARY_RESPONSE
    assert len(router.calls) == 2
    issues = [str(item).lower() for item in result.reflection.issues]
    assert any("capability-is-not-authority" in item for item in issues)
    assert any("unsupported trait/emotion" in item for item in issues)
    assert result.reflection.metadata["mode"] == "character_revision"

    revision_prompt = str(router.calls[1][0][1].content)
    assert "Mary active character contract" in revision_prompt
    assert "Capability is not authority" in revision_prompt
    assert "Do not assign the creator" in revision_prompt


def test_clean_character_consistent_open_ended_reply_does_not_spend_revision_call():
    router = SequenceRouter(first=GOOD_MARY_RESPONSE)
    mary = _mary(router)

    result = mary.process(PHILOSOPHICAL_INPUT)

    assert result.final_response == GOOD_MARY_RESPONSE
    assert len(router.calls) == 1
    assert result.reflection.metadata["mode"] == "local_character_audit"
    assert result.reflection.metadata["llm_calls"] == 0


def test_provider_prompt_carries_stance_not_fictional_autobiography():
    router = SequenceRouter(first=GOOD_MARY_RESPONSE)
    mary = _mary(router)

    mary.process(PHILOSOPHICAL_INPUT)

    combined = "\n".join(str(message.content) for message in router.calls[0][0])
    assert "stance_claims" in combined
    assert "hard_boundaries" in combined
    assert "capability_is_not_authority" in combined
    assert "trusted_peer" in combined
    assert "voice_exemplars" in combined
    assert "creator-authored cadence references" in combined
    assert "Ferrymen" not in combined
    assert "ruby" not in combined.lower()
    assert "Placita Olvera" not in combined


def test_character_dna_selects_distinct_registers_instead_of_one_flat_persona():
    mary = _mary(SequenceRouter(first=GOOD_MARY_RESPONSE))

    samples = {
        "I don't trust him. He keeps lying to us.": "distrust",
        "Roast me, I know that idea was ridiculous.": "playful_banter",
        "I love you, dork.": "affection",
        "That design is gorgeous; the whole color palette works.": "creative_aesthetic",
    }

    for text, expected in samples.items():
        intent = mary.cognition.detect_intent(text)
        mind = mary.turn_mind.build(
            input_text=text,
            intent=intent,
            relevant_memories=[],
            recent_conversation=[],
        ).to_dict()
        names = [item["name"] for item in mind["character_expression"]["active_patterns"]]
        assert expected in names, (text, names)
