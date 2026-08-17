from __future__ import annotations

from mary.cognition.intent import IntentType
from mary.cognition.orchestrator import CognitiveOrchestrator
from mary.core.mary import Mary
from mary.learning.researcher import Researcher
from mary.tools.manager import ToolManager
from mary.tools.web import SearchResult


class FakeSearchProvider:
    def __init__(self) -> None:
        self.calls: list[tuple[str, int]] = []
        self.configured = True

    def search(
        self,
        query: str,
        *,
        limit: int = 10,
        user_agent: str = "",
    ) -> list[SearchResult]:
        self.calls.append((query, limit))
        return [
            SearchResult(
                title="Example Documentation",
                url="https://example.com/docs",
                snippet="Current documentation for the requested topic.",
                source="fake",
            )
        ]


def test_web_search_cannot_bypass_registry_approval(tmp_path):
    manager = ToolManager(
        workspace_root=tmp_path,
    )
    provider = FakeSearchProvider()
    manager.web.search_provider = provider

    result = manager.registry.execute(
        "web_search",
        query="MaryV2 testing",
    )

    assert result.success is False
    assert result.approval_required is True
    assert provider.calls == []


def test_explicit_creator_request_uses_scoped_approval(tmp_path):
    manager = ToolManager(
        workspace_root=tmp_path,
    )
    provider = FakeSearchProvider()
    manager.web.search_provider = provider

    request, result = manager.execute_explicit_creator_request(
        "web_search",
        {"query": "MaryV2 testing", "limit": 3},
        reason="Creator explicitly requested this search.",
    )

    assert result.success is True
    assert request.status == "executed"
    assert provider.calls == [("MaryV2 testing", 3)]

    second_execution = manager.execute_approved(
        request.request_id
    )
    assert second_execution.success is False


def test_researcher_normalizes_search_result_objects():
    researcher = Researcher()
    request = researcher.create_request(
        "MaryV2",
    )

    result = researcher.complete_with_sources(
        request,
        [
            SearchResult(
                title="MaryV2 Source",
                url="https://example.com/mary",
                snippet="A source returned by a web provider.",
            )
        ],
    )

    assert len(result.sources) == 1
    assert result.sources[0].title == "MaryV2 Source"
    assert result.sources[0].url == "https://example.com/mary"
    assert "web provider" in result.sources[0].content


def test_intent_detection_distinguishes_explicit_and_proposed_web_use():
    orchestrator = CognitiveOrchestrator(
        reasoning_engine=object(),
        reflection_engine=object(),
    )

    explicit = orchestrator.detect_intent(
        "search the web for MaryV2 documentation"
    )
    assert explicit.intent_type == IntentType.WEB_SEARCH
    assert explicit.parameters["explicit_creator_request"] is True
    assert explicit.parameters["query"] == "MaryV2 documentation"

    proposed = orchestrator.detect_intent(
        "what is the latest Python release?"
    )
    assert proposed.intent_type == IntentType.WEB_SEARCH
    assert proposed.parameters["explicit_creator_request"] is False


def test_mary_routes_approved_results_through_researcher_and_evaluator():
    mary = Mary()
    provider = FakeSearchProvider()
    mary.tools.web.search_provider = provider

    intent = mary.cognition.detect_intent(
        "look up MaryV2 documentation"
    )

    action = mary._handle_web_intent(
        intent,
        original_input="look up MaryV2 documentation",
    )

    assert "system_response" not in action
    assert len(action["knowledge"]) == 1
    assert len(action["sources"]) == 1
    assert len(mary.researcher.get_results()) == 1
    assert len(mary.evaluator.evaluations) == 1
    assert action["sources"][0]["url"] == "https://example.com/docs"