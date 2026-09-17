from __future__ import annotations

import json
from urllib.parse import parse_qs, urlparse

from mary.tools.manager import ToolManager
from mary.tools.registry import PermissionLevel
from mary.tools.search_backends import (
    FallbackSearchProvider,
    SearXNGSearchProvider,
    build_managed_search_provider,
)
from mary.tools.web import SearchResult


class _Response:
    def __init__(self, payload: dict):
        self._payload = json.dumps(payload).encode("utf-8")

    def __enter__(self):
        return self

    def __exit__(self, exc_type, exc, tb):
        return False

    def read(self) -> bytes:
        return self._payload


class _FailingProvider:
    configured = True

    def search(self, query, *, limit, user_agent):
        raise RuntimeError("offline")


class _WorkingProvider:
    configured = True

    def search(self, query, *, limit, user_agent):
        return [
            SearchResult(
                title="Working result",
                url="https://example.com/result",
                snippet="grounded",
                source="test",
            )
        ]


def test_searxng_configuration_uses_creator_environment(monkeypatch):
    monkeypatch.setenv(
        "MARY_SEARXNG_URL",
        "http://127.0.0.1:8080/",
    )

    provider = SearXNGSearchProvider()

    assert provider.configured is True
    assert provider.base_url == "http://127.0.0.1:8080"


def test_searxng_rejects_embedded_credentials():
    try:
        SearXNGSearchProvider(
            "http://user:password@127.0.0.1:8080"
        )
    except ValueError as exc:
        assert "credentials" in str(exc).lower()
    else:
        raise AssertionError("embedded credentials should be rejected")


def test_searxng_search_uses_json_endpoint_and_normalizes_results(monkeypatch):
    captured = {}

    def fake_urlopen(request, timeout):
        captured["url"] = request.full_url
        captured["timeout"] = timeout
        return _Response(
            {
                "results": [
                    {
                        "title": "<b>Example</b> result",
                        "url": "https://example.com/page",
                        "content": "Useful <em>evidence</em> here.",
                        "score": 2.5,
                        "engines": ["duckduckgo", "brave"],
                        "publishedDate": "2026-09-17T00:00:00Z",
                    }
                ]
            }
        )

    monkeypatch.setattr(
        "mary.tools.search_backends.urllib.request.urlopen",
        fake_urlopen,
    )

    provider = SearXNGSearchProvider(
        "http://127.0.0.1:8080",
        timeout=3.5,
    )
    results = provider.search(
        "Mary grounded search",
        limit=5,
        user_agent="MaryV2/test",
    )

    parsed = urlparse(captured["url"])
    params = parse_qs(parsed.query)

    assert parsed.path == "/search"
    assert params["q"] == ["Mary grounded search"]
    assert params["format"] == ["json"]
    assert captured["timeout"] == 3.5
    assert len(results) == 1
    assert results[0].title == "Example result"
    assert results[0].snippet == "Useful evidence here."
    assert results[0].source == "searxng"
    assert results[0].metadata["provider"] == "searxng"
    assert results[0].metadata["engines"] == ["duckduckgo", "brave"]


def test_local_first_falls_through_and_records_display_safe_route():
    provider = FallbackSearchProvider(
        (_FailingProvider(), _WorkingProvider()),
        name="local_first",
    )

    results = provider.search(
        "test query",
        limit=5,
        user_agent="MaryV2/test",
    )

    assert len(results) == 1
    assert provider.last_backend == "_WorkingProvider"
    assert provider.last_failures[0].error_type == "RuntimeError"
    assert results[0].metadata["search_route"] == "local_first"
    assert results[0].metadata["selected_backend"] == "_WorkingProvider"


def test_managed_provider_preserves_legacy_tavily_brave_ownership(monkeypatch):
    monkeypatch.delenv("MARY_SEARCH_PROVIDER", raising=False)

    assert build_managed_search_provider("tavily") is None
    assert build_managed_search_provider("brave") is None


def test_tool_manager_wires_searxng_without_weakening_tool_permission(
    monkeypatch,
    tmp_path,
):
    monkeypatch.setenv("MARY_SEARCH_PROVIDER", "searxng")
    monkeypatch.setenv("MARY_SEARXNG_URL", "http://127.0.0.1:8080")

    manager = ToolManager(
        workspace_root=tmp_path,
    )

    definition = manager.registry.get("web_search")

    assert isinstance(
        manager.web.search_provider,
        SearXNGSearchProvider,
    )
    assert definition is not None
    assert definition.permission_level == PermissionLevel.APPROVAL_REQUIRED
    assert definition.external_access is True
    assert definition.mutates_state is False
    assert manager.status()["web_search_configured"] is True
    assert manager.status()["web_search_provider"] == "SearXNGSearchProvider"
