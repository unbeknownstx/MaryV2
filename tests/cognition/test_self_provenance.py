from __future__ import annotations

from mary.core.mary import Mary
from mary.llm.interface import LLMResponse


class ProvenanceFakeRouter:
    def __init__(self, responses: list[str]):
        self.responses = list(responses)
        self.calls = []

    def generate(self, messages, **kwargs):
        self.calls.append((messages, kwargs))
        content = self.responses.pop(0) if self.responses else "Okay."
        return LLMResponse(
            content=content,
            provider="test",
            model="provenance-fake",
            finish_reason="stop",
            usage={},
        )

    def provider_name(self, provider=None):
        return "test"

    def model_name(self, provider=None):
        return "provenance-fake"

    def is_available(self, provider=None):
        return True


def _mary(router: ProvenanceFakeRouter | None = None) -> Mary:
    mary = Mary()
    if router is not None:
        mary.llm = router
        mary.reasoning.llm = router
        mary.reflection.llm = router
    return mary


def test_self_provenance_classifies_authored_and_developed_state():
    mary = _mary()

    initial = mary.self_provenance.snapshot()
    assert initial["policy"]["model_output_is_persistence_source"] is False
    assert initial["source_map"]["model_dialogue"] == "situational"
    assert any(
        item["domain"] == "appearance"
        and item["key"] == "Hair color"
        and item["provenance"] == "canonical"
        for item in initial["canonical"]
    )
    assert any(
        item["domain"] == "preference"
        and item["key"] == "drawing"
        and item["provenance"] == "canonical"
        for item in initial["canonical"]
    )

    mary.preferences.set_preference(
        "lavender",
        category="scent",
        strength=0.7,
        polarity=1.0,
        confidence=0.9,
        source="experience",
    )
    developed = mary.self_provenance.snapshot()["developed"]
    assert any(
        item["domain"] == "preference"
        and item["key"] == "lavender"
        and item["provenance"] == "developed"
        for item in developed
    )


def test_turn_mind_exposes_explicit_non_persistence_boundary():
    mary = _mary()
    result = mary.process("Hey Mary")
    provenance = result.context.mind_state["self_provenance"]

    assert provenance["policy"]["situational_imagination_is_allowed"] is True
    assert provenance["policy"]["situational_imagination_is_persisted"] is False
    assert provenance["policy"]["durable_change_requires_explicit_system_path"] is True


def test_harmless_hypothetical_imagination_is_not_flagged_or_persisted():
    router = ProvenanceFakeRouter([
        "Maybe I'd light a lavender candle and bake cookies if that was the mood."
    ])
    mary = _mary(router)

    assert mary.preferences.get_preference("lavender") is None
    result = mary.process("What would your perfect lazy day look like?")

    assert result.reasoning.metadata["self_provenance_issue"] is None
    assert result.reasoning.metadata["self_provenance_policy"] == "model_output_is_situational_until_promoted"
    assert mary.preferences.get_preference("lavender") is None
    assert len(router.calls) == 1


def test_unsupported_permanent_self_claim_is_audited_and_revised_not_persisted():
    router = ProvenanceFakeRouter([
        "I'd bake cookies and toss in sunflower seeds because I'm a secret health nut.",
        "I'd bake cookies and maybe toss in sunflower seeds if I felt like it.",
    ])
    mary = _mary(router)

    result = mary.process("What would your perfect lazy day look like?")

    issue = result.reasoning.metadata["self_provenance_issue"]
    assert issue is not None
    assert "secret health nut" in issue.lower()
    assert result.reflection.decision.value == "revise"
    assert result.final_response == "I'd bake cookies and maybe toss in sunflower seeds if I felt like it."
    assert mary.preferences.get_preference("health nut") is None
    assert mary.preferences.get_preference("sunflower seeds") is None
    assert len(router.calls) == 2
