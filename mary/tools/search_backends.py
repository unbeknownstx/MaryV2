"""Managed search backends for Mary's existing web-evidence capability.

This module extends, rather than replaces, :mod:`mary.tools.web`.

The authority boundary stays unchanged:

    creator request / approved tool request
        -> ToolRegistry web_search
        -> WebClient
        -> configured search provider
        -> Researcher / source resolution / grounding / evaluation
        -> temporary evidence in cognition

Search providers are retrieval mechanisms only. They do not write memory,
change Mary state, or bypass ToolRegistry approval.
"""

from __future__ import annotations

from dataclasses import dataclass
import json
import os
from typing import Any, Iterable
from urllib.parse import urlencode, urlparse
import urllib.error
import urllib.request

from .web import (
    BraveSearchProvider,
    SearchResult,
    TavilySearchProvider,
    _clean_search_text,
)


@dataclass(frozen=True)
class SearchBackendFailure:
    """Display-safe record of one failed fallback attempt."""

    backend: str
    error_type: str


class SearXNGSearchProvider:
    """Search a creator-configured SearXNG instance.

    SearXNG is useful for Mary's local-first deployments because the metasearch
    service can be self-hosted and does not require an API key. Mary does not
    assume that a SearXNG service exists: ``MARY_SEARXNG_URL`` (or the legacy
    ``SEARXNG_URL`` alias) must be configured explicitly.

    The URL is process configuration, not model-controlled input. Only HTTP(S)
    endpoints without embedded credentials are accepted.
    """

    def __init__(
        self,
        base_url: str | None = None,
        *,
        timeout: float = 10.0,
        language: str = "en",
        safesearch: int = 1,
    ) -> None:
        configured_url = (
            base_url
            if base_url is not None
            else (
                os.getenv("MARY_SEARXNG_URL")
                or os.getenv("SEARXNG_URL")
                or ""
            )
        )
        self.base_url = self._normalize_base_url(configured_url)
        self.timeout = float(timeout)
        self.language = str(language or "en")
        self.safesearch = max(0, min(2, int(safesearch)))

    @property
    def configured(self) -> bool:
        return bool(self.base_url)

    def search(
        self,
        query: str,
        *,
        limit: int = 10,
        user_agent: str = "MaryV2/0.1",
    ) -> list[SearchResult]:
        """Search through the configured SearXNG JSON endpoint."""

        if not self.configured:
            raise RuntimeError(
                "SearXNG Search is not configured. Set MARY_SEARXNG_URL "
                "to the base URL of a SearXNG instance."
            )

        query = str(query).strip()
        if not query:
            raise ValueError("Search query cannot be empty.")

        count = max(1, min(int(limit), 20))
        params = urlencode(
            {
                "q": query,
                "format": "json",
                "language": self.language,
                "safesearch": self.safesearch,
            }
        )
        endpoint = f"{self.base_url}/search?{params}"
        request = urllib.request.Request(
            endpoint,
            headers={
                "Accept": "application/json",
                "User-Agent": user_agent,
            },
            method="GET",
        )

        try:
            with urllib.request.urlopen(
                request,
                timeout=self.timeout,
            ) as response:
                payload = json.loads(
                    response.read().decode("utf-8")
                )
        except urllib.error.HTTPError as exc:
            detail = ""
            try:
                detail = exc.read().decode(
                    "utf-8",
                    errors="replace",
                )
            except Exception:
                detail = ""
            raise RuntimeError(
                f"SearXNG Search HTTP {exc.code}: "
                f"{detail[:500] or exc.reason}"
            ) from exc
        except urllib.error.URLError as exc:
            raise RuntimeError(
                f"SearXNG Search network error: {exc.reason}"
            ) from exc
        except (UnicodeDecodeError, json.JSONDecodeError) as exc:
            raise RuntimeError(
                "SearXNG Search returned an invalid JSON response."
            ) from exc

        return self._parse_results(
            payload,
            limit=count,
        )

    def _parse_results(
        self,
        payload: dict[str, Any],
        *,
        limit: int,
    ) -> list[SearchResult]:
        results: list[SearchResult] = []
        raw_results = payload.get("results", [])

        for rank, item in enumerate(raw_results, start=1):
            if not isinstance(item, dict):
                continue

            title = _clean_search_text(item.get("title", ""))
            url = str(item.get("url", "")).strip()
            snippet = _clean_search_text(item.get("content", ""))
            if not title and not url:
                continue

            engines = item.get("engines")
            if isinstance(engines, (list, tuple)):
                engine_names = [
                    str(value).strip()
                    for value in engines
                    if str(value).strip()
                ]
            else:
                single_engine = str(item.get("engine", "")).strip()
                engine_names = [single_engine] if single_engine else []

            results.append(
                SearchResult(
                    title=title or url,
                    url=url,
                    snippet=snippet,
                    content=snippet,
                    source="searxng",
                    metadata={
                        "provider": "searxng",
                        "rank": rank,
                        "score": item.get("score"),
                        "published_date": (
                            item.get("publishedDate")
                            or item.get("published_date")
                        ),
                        "category": item.get("category"),
                        "engines": engine_names,
                        "result_type": "web",
                        "content_source": "snippet",
                    },
                )
            )

            if len(results) >= limit:
                break

        return results

    @staticmethod
    def _normalize_base_url(value: str | None) -> str:
        text = str(value or "").strip().rstrip("/")
        if not text:
            return ""

        parsed = urlparse(text)
        if parsed.scheme.lower() not in {"http", "https"}:
            raise ValueError(
                "MARY_SEARXNG_URL must use http:// or https://."
            )
        if not parsed.hostname:
            raise ValueError(
                "MARY_SEARXNG_URL must include a hostname."
            )
        if parsed.username is not None or parsed.password is not None:
            raise ValueError(
                "MARY_SEARXNG_URL cannot contain embedded credentials."
            )
        if parsed.query or parsed.fragment:
            raise ValueError(
                "MARY_SEARXNG_URL must be a base URL without a query or fragment."
            )
        return text


class FallbackSearchProvider:
    """Try configured read-only search providers in a deterministic order."""

    def __init__(
        self,
        providers: Iterable[Any],
        *,
        name: str = "local_first",
    ) -> None:
        self.providers = tuple(providers)
        self.name = str(name or "fallback")
        self.last_failures: tuple[SearchBackendFailure, ...] = ()
        self.last_backend: str | None = None

    @property
    def configured(self) -> bool:
        return any(
            bool(getattr(provider, "configured", False))
            for provider in self.providers
        )

    def search(
        self,
        query: str,
        *,
        limit: int = 10,
        user_agent: str = "MaryV2/0.1",
    ) -> list[SearchResult]:
        failures: list[SearchBackendFailure] = []
        configured = [
            provider
            for provider in self.providers
            if bool(getattr(provider, "configured", False))
        ]

        if not configured:
            raise RuntimeError(
                "No search backend in the local-first chain is configured. "
                "Set MARY_SEARXNG_URL, TAVILY_API_KEY, or BRAVE_API_KEY."
            )

        for provider in configured:
            backend = self._backend_name(provider)
            try:
                results = provider.search(
                    query,
                    limit=limit,
                    user_agent=user_agent,
                )
            except Exception as exc:
                failures.append(
                    SearchBackendFailure(
                        backend=backend,
                        error_type=type(exc).__name__,
                    )
                )
                continue

            normalized = list(results or [])[: max(1, min(int(limit), 20))]
            if not normalized:
                failures.append(
                    SearchBackendFailure(
                        backend=backend,
                        error_type="empty_results",
                    )
                )
                continue

            self.last_backend = backend
            self.last_failures = tuple(failures)
            for item in normalized:
                if isinstance(getattr(item, "metadata", None), dict):
                    item.metadata.setdefault("search_route", self.name)
                    item.metadata.setdefault("selected_backend", backend)
            return normalized

        self.last_backend = None
        self.last_failures = tuple(failures)
        summary = ", ".join(
            f"{failure.backend}:{failure.error_type}"
            for failure in failures
        ) or "no usable result"
        raise RuntimeError(
            "All configured search backends failed: " + summary
        )

    @staticmethod
    def _backend_name(provider: Any) -> str:
        if isinstance(provider, SearXNGSearchProvider):
            return "searxng"
        if isinstance(provider, TavilySearchProvider):
            return "tavily"
        if isinstance(provider, BraveSearchProvider):
            return "brave"
        return type(provider).__name__


def build_managed_search_provider(
    configured_name: str | None,
    *,
    timeout: float = 10.0,
) -> Any | None:
    """Resolve Mary-only search modes that are not owned by legacy ``web.py``.

    ``None`` means the caller should use ``mary.tools.web.create_search_provider``
    unchanged. This preserves all existing Tavily/Brave behavior.

    New modes:

    - ``searxng``: require the creator-configured SearXNG service.
    - ``local_first`` / ``auto``: SearXNG -> Tavily -> Brave, skipping providers
      that are not configured and falling through on read failures/empty results.
    """

    requested = (
        os.getenv("MARY_SEARCH_PROVIDER")
        or configured_name
        or "tavily"
    )
    requested = str(requested).strip().lower()

    if requested == "searxng":
        return SearXNGSearchProvider(
            timeout=timeout,
        )

    if requested in {"local_first", "auto"}:
        return FallbackSearchProvider(
            (
                SearXNGSearchProvider(timeout=timeout),
                TavilySearchProvider(timeout=timeout),
                BraveSearchProvider(timeout=timeout),
            ),
            name="local_first",
        )

    return None
