from __future__ import annotations

from mary.tools.web import (
    BraveSearchProvider,
    TavilySearchProvider,
    WebClient,
    WebConfig,
    create_search_provider,
)


def test_tavily_is_default_search_provider(monkeypatch):
    monkeypatch.delenv("MARY_SEARCH_PROVIDER", raising=False)

    client = WebClient(
        config=WebConfig(
            search_provider="tavily",
        )
    )

    assert isinstance(
        client.search_provider,
        TavilySearchProvider,
    )


def test_search_provider_can_be_selected_by_environment(monkeypatch):
    monkeypatch.setenv(
        "MARY_SEARCH_PROVIDER",
        "brave",
    )

    provider = create_search_provider()

    assert isinstance(
        provider,
        BraveSearchProvider,
    )


def test_tavily_configuration_uses_environment_key(monkeypatch):
    monkeypatch.setenv(
        "TAVILY_API_KEY",
        "tvly-test-key",
    )

    provider = TavilySearchProvider()

    assert provider.configured is True
    assert provider.api_key == "tvly-test-key"


def test_tavily_result_normalization():
    provider = TavilySearchProvider(
        api_key="tvly-test-key",
    )

    results = provider._parse_results(
        {
            "results": [
                {
                    "title": "Example Result",
                    "url": "https://example.com",
                    "content": "Useful search content.",
                    "score": 0.91,
                }
            ]
        },
        limit=5,
    )

    assert len(results) == 1
    assert results[0].title == "Example Result"
    assert results[0].url == "https://example.com"
    assert results[0].snippet == "Useful search content."
    assert results[0].source == "tavily"
    assert results[0].metadata["provider"] == "tavily"
    assert results[0].metadata["score"] =