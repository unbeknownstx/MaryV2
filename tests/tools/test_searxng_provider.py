from __future__ import annotations

from mary.knowledge.gateway import KnowledgeGateway, SearXNGAdapter
from mary.tools.web import SearXNGSearchProvider, create_search_provider


def test_create_search_provider_supports_searxng(monkeypatch):
    monkeypatch.delenv("MARY_SEARCH_PROVIDER", raising=False)
    monkeypatch.setenv("MARY_SEARXNG_URL", "http://127.0.0.1:8080")

    provider = create_search_provider("searxng")

    assert isinstance(provider, SearXNGSearchProvider)
    assert provider.configured is True


def test_search_provider_environment_can_select_searxng(monkeypatch):
    monkeypatch.setenv("MARY_SEARCH_PROVIDER", "searxng")
    monkeypatch.setenv("MARY_SEARXNG_URL", "http://localhost:8080")

    provider = create_search_provider("tavily")

    assert isinstance(provider, SearXNGSearchProvider)
    assert provider.base_url == "http://localhost:8080"


def test_default_knowledge_gateway_does_not_duplicate_general_web_searxng():
    gateway = KnowledgeGateway()

    assert not any(isinstance(adapter, SearXNGAdapter) for adapter in gateway.adapters)
    assert {adapter.name for adapter in gateway.adapters} == {
        "wikipedia",
        "openalex",
        "crossref",
        "semantic_scholar",
    }
