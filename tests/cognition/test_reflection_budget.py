from mary.core.mary import Mary
from mary.llm.interface import LLMResponse
from mary.tools.web import SearchResult


class FakeSearchProvider:
    configured = True

    def search(self, query, *, limit=10, user_agent=""):
        return [
            SearchResult(
                title="Python 3.15.0rc1",
                url="https://www.python.org/downloads/release/python-3150rc1/",
                snippet=(
                    "Python 3.15.0rc1 is a preview release released "
                    "August 4, 2026."
                ),
                source="fake",
                metadata={
                    "published_date": "2026-08-04",
                    "score": 0.95,
                },
            )
        ]


class FakeRouter:
    def __init__(self):
        self.calls = []

    def generate(self, messages, provider=None, temperature=None, max_tokens=None):
        self.calls.append(messages)
        joined = "\n".join(message.content for message in messages)

        if "Grounding rules:" in joined:
            return LLMResponse(
                content=(
                    "Python 3.15.0rc1 is a preview release. The retrieved "
                    "official source says it was released August 4, 2026."
                ),
                provider="test",
                model="fake",
            )

        return LLMResponse(
            content="Unexpected extra LLM call.",
            provider="test",
            model="fake",
        )

    def provider_name(self, provider=None):
        return "test"

    def model_name(self, provider=None):
        return "fake"

    def is_available(self, provider=None):
        return True


def test_live_research_path_repairs_draft_before_final_response():
    mary = Mary()
    fake = FakeRouter()

    mary.llm = fake
    mary.reasoning.llm = fake
    mary.reflection.llm = fake
    mary.evaluator.llm = fake
    mary.tools.web.search_provider = FakeSearchProvider()

    result = mary.process(
        "search the web for the latest Python release"
    )

    assert "preview release" in result.final_response
    assert "rolling out" not in result.final_response
    assert "Sources:" in result.final_response
    assert result.reasoning.metadata["evidence_validation"]["validated"] is True
    assert result.reasoning.metadata["research_mode"] == "single_pass_grounded_synthesis"
    assert result.reflection.metadata["mode"] == "evidence_validation_reuse"
    assert len(fake.calls) == 1
    assert mary.reasoning.evidence_validator is mary.evidence_validator