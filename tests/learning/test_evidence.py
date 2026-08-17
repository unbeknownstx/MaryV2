from mary.learning.evidence import ClaimGrounder, EvidenceValidator
from mary.llm.interface import LLMResponse


def _knowledge(
    *,
    title="Python 3.15.0rc1",
    url="https://www.python.org/downloads/release/python-3150rc1/",
    content="Python 3.15.0rc1 is a preview release released August 4, 2026.",
    primary=True,
    stale=False,
    overall=0.9,
    recommendation="accept",
):
    return {
        "title": title,
        "url": url,
        "content": content,
        "source_type": "web",
        "research_grounding": {
            "overall": overall,
            "primary_source": primary,
            "observed_date": "2026-08-04",
            "stale_for_dynamic_query": stale,
        },
        "evaluation": {
            "recommendation": recommendation,
            "confidence": 0.9,
            "reliability": 0.9,
        },
    }


def test_claim_grounder_prefers_primary_current_evidence_and_rejects_rejected_sources():
    grounder = ClaimGrounder()

    rejected = _knowledge(
        title="Rejected",
        url="https://bad.example/post",
        primary=False,
        overall=1.0,
        recommendation="reject",
    )
    stale = _knowledge(
        title="Old article",
        url="https://example.com/old",
        primary=False,
        stale=True,
        overall=0.95,
    )
    official = _knowledge()

    bundle = grounder.build_bundle(
        "latest Python release",
        [rejected, stale, official],
    )

    assert bundle.dynamic_query is True
    assert [item.title for item in bundle.items] == [
        "Python 3.15.0rc1",
        "Old article",
    ]


class AuditLLM:
    def __init__(self):
        self.messages = []
        self.kwargs = []

    def generate(self, messages, **kwargs):
        self.messages.append(messages)
        self.kwargs.append(kwargs)
        return LLMResponse(
            content=(
                "Python 3.15.0rc1 is a preview release; the evidence says it "
                "was released August 4, 2026."
            ),
            provider="test",
            model="audit",
        )


def test_evidence_validator_repairs_unsupported_stronger_wording():
    llm = AuditLLM()
    validator = EvidenceValidator()

    result = validator.validate(
        query="what is the latest Python release?",
        draft="Python 3.15 is already rolling out.",
        knowledge=[_knowledge()],
        llm=llm,
    )

    assert result.validated is True
    assert result.changed is True
    assert "preview release" in result.response
    assert "rolling out" not in result.response
    assert len(llm.messages[0]) == 1
    assert llm.messages[0][0].role == "user"
    assert "EVIDENCE AUDIT" in llm.messages[0][0].content
    assert "does not support saying a version is generally released" in llm.messages[0][0].content
    assert llm.kwargs[0]["temperature"] == 0.5
    assert llm.kwargs[0]["max_tokens"] == 2400


class BrokenAuditLLM:
    def generate(self, messages, **kwargs):
        raise RuntimeError("validator unavailable")


def test_evidence_validator_falls_back_to_evidence_if_audit_cannot_run():
    result = EvidenceValidator().validate(
        query="latest Python release",
        draft="Unsupported answer",
        knowledge=[_knowledge()],
        llm=BrokenAuditLLM(),
    )

    assert result.validated is False
    assert result.changed is True
    assert result.failure == "RuntimeError"
    assert result.metadata["fallback"] == "evidence_only"
    assert "strongest retrieved source excerpts" in result.response
    assert "Python 3.15.0rc1" in result.response
    assert "Unsupported answer" not in result.response


class BlankThenValidAuditLLM:
    def __init__(self):
        self.calls = []

    def generate(self, messages, **kwargs):
        self.calls.append(kwargs)
        if len(self.calls) == 1:
            return LLMResponse(
                content="",
                provider="test",
                model="reasoning",
                finish_reason="length",
                usage={"completion_tokens": 2400},
            )
        return LLMResponse(
            content="Python 3.15.0rc1 is a preview release.",
            provider="test",
            model="reasoning",
            finish_reason="stop",
        )


def test_evidence_validator_retries_blank_reasoning_model_completion_with_more_budget():
    llm = BlankThenValidAuditLLM()

    result = EvidenceValidator().validate(
        query="latest Python release",
        draft="Python 3.15 is rolling out.",
        knowledge=[_knowledge()],
        llm=llm,
    )

    assert result.validated is True
    assert result.response == "Python 3.15.0rc1 is a preview release."
    assert [call["max_tokens"] for call in llm.calls] == [2400, 3200]
    assert len(result.metadata["attempts"]) == 2


class AlwaysBlankAuditLLM:
    def generate(self, messages, **kwargs):
        return LLMResponse(
            content="",
            provider="test",
            model="reasoning",
            finish_reason="length",
        )


def test_evidence_validator_blank_twice_uses_evidence_only_fallback_not_dead_end():
    result = EvidenceValidator().validate(
        query="latest Python release",
        draft="Python 3.15 is rolling out.",
        knowledge=[_knowledge()],
        llm=AlwaysBlankAuditLLM(),
    )

    assert result.validated is False
    assert result.failure == "empty_validator_response"
    assert result.metadata["fallback"] == "evidence_only"
    assert "Python 3.15.0rc1" in result.response
    assert "rolling out" not in result.response


class SynthesisLLM:
    def __init__(self):
        self.calls = []

    def generate(self, messages, **kwargs):
        self.calls.append((messages, kwargs))
        return LLMResponse(
            content=(
                "Python 3.15.0rc1 is a preview release released "
                "August 4, 2026."
            ),
            provider="test",
            model="synthesis",
        )


def test_evidence_synthesis_is_single_call_and_compacts_large_sources():
    llm = SynthesisLLM()
    validator = EvidenceValidator()

    huge = "Python release evidence. " * 1000
    knowledge = [
        _knowledge(
            title=f"Source {index}",
            url=f"https://www.python.org/source-{index}",
            content=huge,
            overall=0.95 - (index * 0.01),
        )
        for index in range(6)
    ]

    result = validator.synthesize(
        query="latest Python release",
        knowledge=knowledge,
        llm=llm,
    )

    assert result.validated is True
    assert result.metadata["mode"] == "evidence_synthesis"
    assert len(llm.calls) == 1

    messages, kwargs = llm.calls[0]
    prompt = messages[0].content

    assert len(messages) == 1
    assert kwargs["max_tokens"] == 4096
    assert prompt.count("SOURCE ") == 4
    assert len(prompt) < 9000


class BrokenSynthesisLLM:
    def generate(self, messages, **kwargs):
        raise RuntimeError("provider unavailable")


def test_evidence_synthesis_fails_closed_to_evidence_only_fallback():
    result = EvidenceValidator().synthesize(
        query="latest Python release",
        knowledge=[_knowledge()],
        llm=BrokenSynthesisLLM(),
    )

    assert result.validated is False
    assert result.metadata["mode"] == "evidence_synthesis"
    assert result.metadata["fallback"] == "evidence_only"
    assert "Python 3.15.0rc1" in result.response