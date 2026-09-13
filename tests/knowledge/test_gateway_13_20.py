from mary.knowledge.gateway import (
    CrossrefAdapter,
    KnowledgeGateway,
    OpenAlexAdapter,
    SearXNGAdapter,
    SemanticScholarAdapter,
    WikipediaAdapter,
)


def fake_fetch(url: str, headers: dict[str, str]):
    if "wikipedia.org" in url:
        return {"query": {"search": [{"title": "Artificial intelligence", "pageid": 1, "snippet": "AI overview"}]}}
    if "openalex.org" in url:
        return {"results": [{
            "id": "https://openalex.org/W1",
            "display_name": "A paper",
            "publication_year": 2025,
            "authorships": [{"author": {"display_name": "Researcher One"}}],
            "primary_location": {"landing_page_url": "https://example.org/a"},
            "cited_by_count": 12,
            "open_access": {"is_oa": True},
        }]}
    if "crossref.org" in url:
        return {"message": {"items": [{
            "DOI": "10.1/test",
            "title": ["Crossref paper"],
            "URL": "https://doi.org/10.1/test",
            "published": {"date-parts": [[2024, 1, 1]]},
            "author": [{"given": "Jane", "family": "Doe"}],
            "type": "journal-article",
        }]}}
    if "semanticscholar.org" in url:
        return {"data": [{
            "paperId": "S1",
            "title": "Semantic paper",
            "url": "https://example.org/s1",
            "abstract": "Useful abstract",
            "year": 2026,
            "authors": [{"name": "A. Scholar"}],
            "citationCount": 4,
        }]}
    return {"results": [{"title": "Web result", "url": "https://example.org/web", "content": "web snippet", "engine": "test"}]}


def test_gateway_normalizes_multiple_public_sources_without_network():
    adapters = [
        WikipediaAdapter(fetch_json=fake_fetch),
        OpenAlexAdapter(fetch_json=fake_fetch),
        CrossrefAdapter(fetch_json=fake_fetch),
        SemanticScholarAdapter(fetch_json=fake_fetch),
        SearXNGAdapter(base_url="http://127.0.0.1:8088", fetch_json=fake_fetch),
    ]
    results = KnowledgeGateway(adapters).search("AI", limit_per_source=2)
    assert {item["source"] for item in results} == {
        "wikipedia", "openalex", "crossref", "semantic_scholar", "searxng"
    }


def test_category_filter_only_queries_academic_adapters():
    calls: list[str] = []

    def tracking_fetch(url: str, headers: dict[str, str]):
        calls.append(url)
        return fake_fetch(url, headers)

    gateway = KnowledgeGateway([
        WikipediaAdapter(fetch_json=tracking_fetch),
        OpenAlexAdapter(fetch_json=tracking_fetch),
        CrossrefAdapter(fetch_json=tracking_fetch),
    ])
    results = gateway.search("memory systems", categories=["academic"])
    assert {item["source"] for item in results} == {"openalex", "crossref"}
    assert all("wikipedia" not in url for url in calls)


def test_searxng_is_disabled_without_explicit_safe_endpoint(monkeypatch):
    monkeypatch.delenv("MARY_SEARXNG_URL", raising=False)
    adapter = SearXNGAdapter(fetch_json=fake_fetch)
    assert adapter.available() is False
    assert adapter.search("anything") == []


def test_gateway_status_declares_external_evidence_boundary():
    gateway = KnowledgeGateway([WikipediaAdapter(fetch_json=fake_fetch)])
    status = gateway.status()
    assert status["authority"] == "external_evidence_only"
    assert status["startup_network_dependency"] is False
