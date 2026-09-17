"""Optional federated public-knowledge gateway for MaryV2.

This module is deliberately outside canonical memory authority. It performs
bounded, on-demand retrieval from public knowledge services and returns normalized
source records. No network call occurs at import/startup time, and every adapter
can be disabled independently.
"""
from __future__ import annotations

from dataclasses import asdict, dataclass
import json
import os
from typing import Any, Callable, Iterable
from urllib.parse import urlencode
from urllib.request import Request, urlopen


JsonFetcher = Callable[[str, dict[str, str]], dict[str, Any]]


def _default_fetch_json(url: str, headers: dict[str, str]) -> dict[str, Any]:
    request = Request(url, headers={"User-Agent": "MaryV2-Knowledge/13.20", **headers})
    with urlopen(request, timeout=8.0) as response:  # noqa: S310 - fixed HTTPS adapters only
        payload = response.read(2_000_000)
    data = json.loads(payload.decode("utf-8"))
    return data if isinstance(data, dict) else {}


def _text(value: Any, limit: int = 1200) -> str:
    return " ".join(str(value or "").split())[:limit]


@dataclass(frozen=True)
class KnowledgeResult:
    source: str
    title: str
    url: str
    snippet: str = ""
    identifier: str = ""
    year: int | None = None
    authors: tuple[str, ...] = ()
    metadata: dict[str, Any] | None = None

    def to_dict(self) -> dict[str, Any]:
        result = asdict(self)
        result["authors"] = list(self.authors)
        return result


class KnowledgeAdapter:
    name = "base"
    category = "general"
    requires_key = False

    def __init__(self, *, fetch_json: JsonFetcher | None = None) -> None:
        self.fetch_json = fetch_json or _default_fetch_json

    def available(self) -> bool:
        return True

    def search(self, query: str, *, limit: int = 5) -> list[KnowledgeResult]:
        raise NotImplementedError

    @staticmethod
    def _limit(limit: int) -> int:
        return max(1, min(10, int(limit)))


class WikipediaAdapter(KnowledgeAdapter):
    name = "wikipedia"
    category = "encyclopedic"
    BASE = "https://en.wikipedia.org/w/api.php"

    def search(self, query: str, *, limit: int = 5) -> list[KnowledgeResult]:
        params = urlencode({
            "action": "query",
            "list": "search",
            "srsearch": str(query),
            "srlimit": self._limit(limit),
            "format": "json",
            "utf8": 1,
        })
        data = self.fetch_json(f"{self.BASE}?{params}", {})
        rows = ((data.get("query") or {}).get("search") or []) if isinstance(data, dict) else []
        results: list[KnowledgeResult] = []
        for row in rows:
            if not isinstance(row, dict):
                continue
            title = _text(row.get("title"), 240)
            if not title:
                continue
            results.append(KnowledgeResult(
                source=self.name,
                title=title,
                url="https://en.wikipedia.org/wiki/" + title.replace(" ", "_"),
                snippet=_text(row.get("snippet")),
                identifier=str(row.get("pageid") or ""),
            ))
        return results


class OpenAlexAdapter(KnowledgeAdapter):
    name = "openalex"
    category = "academic"
    BASE = "https://api.openalex.org/works"

    def search(self, query: str, *, limit: int = 5) -> list[KnowledgeResult]:
        params: dict[str, Any] = {"search": str(query), "per-page": self._limit(limit)}
        key = os.getenv("OPENALEX_API_KEY", "").strip()
        if key:
            params["api_key"] = key
        data = self.fetch_json(f"{self.BASE}?{urlencode(params)}", {})
        results: list[KnowledgeResult] = []
        for row in data.get("results", []) if isinstance(data, dict) else []:
            if not isinstance(row, dict):
                continue
            authors = tuple(
                _text(((item.get("author") or {}).get("display_name")), 120)
                for item in row.get("authorships", [])[:8]
                if isinstance(item, dict) and _text(((item.get("author") or {}).get("display_name")), 120)
            )
            primary = row.get("primary_location") or {}
            results.append(KnowledgeResult(
                source=self.name,
                title=_text(row.get("display_name") or row.get("title"), 400),
                url=_text(primary.get("landing_page_url") or row.get("doi") or row.get("id"), 700),
                identifier=_text(row.get("id"), 200),
                year=(int(row["publication_year"]) if row.get("publication_year") else None),
                authors=authors,
                metadata={"cited_by_count": row.get("cited_by_count"), "open_access": row.get("open_access")},
            ))
        return results


class CrossrefAdapter(KnowledgeAdapter):
    name = "crossref"
    category = "academic"
    BASE = "https://api.crossref.org/works"

    def search(self, query: str, *, limit: int = 5) -> list[KnowledgeResult]:
        params: dict[str, Any] = {"query.bibliographic": str(query), "rows": self._limit(limit)}
        mailto = os.getenv("CROSSREF_MAILTO", "").strip()
        if mailto:
            params["mailto"] = mailto
        data = self.fetch_json(f"{self.BASE}?{urlencode(params)}", {})
        items = ((data.get("message") or {}).get("items") or []) if isinstance(data, dict) else []
        results: list[KnowledgeResult] = []
        for row in items:
            if not isinstance(row, dict):
                continue
            titles = row.get("title") or []
            title = _text(titles[0] if titles else "", 400)
            authors = tuple(
                _text(" ".join(filter(None, [item.get("given"), item.get("family")])), 120)
                for item in row.get("author", [])[:8]
                if isinstance(item, dict)
            )
            year = None
            parts = (((row.get("published") or {}).get("date-parts") or [[None]])[0])
            if parts and parts[0]:
                try:
                    year = int(parts[0])
                except (TypeError, ValueError):
                    year = None
            doi = _text(row.get("DOI"), 200)
            results.append(KnowledgeResult(
                source=self.name,
                title=title,
                url=_text(row.get("URL") or (f"https://doi.org/{doi}" if doi else ""), 700),
                identifier=doi,
                year=year,
                authors=tuple(item for item in authors if item),
                metadata={"type": row.get("type"), "publisher": row.get("publisher")},
            ))
        return results


class SemanticScholarAdapter(KnowledgeAdapter):
    name = "semantic_scholar"
    category = "academic"
    BASE = "https://api.semanticscholar.org/graph/v1/paper/search"

    def search(self, query: str, *, limit: int = 5) -> list[KnowledgeResult]:
        params = urlencode({
            "query": str(query),
            "limit": self._limit(limit),
            "fields": "title,url,abstract,authors,year,citationCount,openAccessPdf",
        })
        headers: dict[str, str] = {}
        key = os.getenv("SEMANTIC_SCHOLAR_API_KEY", "").strip()
        if key:
            headers["x-api-key"] = key
        data = self.fetch_json(f"{self.BASE}?{params}", headers)
        results: list[KnowledgeResult] = []
        for row in data.get("data", []) if isinstance(data, dict) else []:
            if not isinstance(row, dict):
                continue
            authors = tuple(_text(item.get("name"), 120) for item in row.get("authors", [])[:8] if isinstance(item, dict))
            results.append(KnowledgeResult(
                source=self.name,
                title=_text(row.get("title"), 400),
                url=_text(row.get("url"), 700),
                snippet=_text(row.get("abstract")),
                identifier=_text(row.get("paperId"), 200),
                year=(int(row["year"]) if row.get("year") else None),
                authors=tuple(item for item in authors if item),
                metadata={"citation_count": row.get("citationCount"), "open_access_pdf": row.get("openAccessPdf")},
            ))
        return results


class SearXNGAdapter(KnowledgeAdapter):
    """Backward-compatible explicit adapter; not part of the default gateway.

    General web retrieval is canonically owned by ``mary.tools.web``. Keeping
    this adapter importable avoids breaking older integrations while preventing
    one SearXNG service from being exposed by two default approval-gated tools.
    """

    name = "searxng"
    category = "web"

    def __init__(self, *, base_url: str | None = None, fetch_json: JsonFetcher | None = None) -> None:
        super().__init__(fetch_json=fetch_json)
        self.base_url = str(base_url or os.getenv("MARY_SEARXNG_URL", "")).strip().rstrip("/")

    def available(self) -> bool:
        return self.base_url.startswith("http://127.0.0.1") or self.base_url.startswith("http://localhost") or self.base_url.startswith("https://")

    def search(self, query: str, *, limit: int = 5) -> list[KnowledgeResult]:
        if not self.available():
            return []
        url = f"{self.base_url}/search?{urlencode({'q': str(query), 'format': 'json'})}"
        data = self.fetch_json(url, {})
        results: list[KnowledgeResult] = []
        for row in (data.get("results") or [])[: self._limit(limit)]:
            if not isinstance(row, dict):
                continue
            results.append(KnowledgeResult(
                source=self.name,
                title=_text(row.get("title"), 400),
                url=_text(row.get("url"), 700),
                snippet=_text(row.get("content")),
                metadata={"engine": row.get("engine"), "engines": row.get("engines")},
            ))
        return results


class KnowledgeGateway:
    """Route explicit knowledge lookup to bounded optional adapters."""

    VERSION = "13.20"

    def __init__(self, adapters: Iterable[KnowledgeAdapter] | None = None) -> None:
        # General web search belongs to mary.tools.web. This gateway defaults to
        # bounded encyclopedic/academic sources only; SearXNGAdapter remains
        # available for explicit backward-compatible construction.
        self.adapters = list(adapters) if adapters is not None else [
            WikipediaAdapter(), OpenAlexAdapter(), CrossrefAdapter(), SemanticScholarAdapter()
        ]

    def search(self, query: str, *, categories: Iterable[str] | None = None, limit_per_source: int = 4) -> list[dict[str, Any]]:
        allowed = {str(item).strip().lower() for item in categories or [] if str(item).strip()}
        combined: list[KnowledgeResult] = []
        for adapter in self.adapters:
            if allowed and adapter.category not in allowed and adapter.name not in allowed:
                continue
            if not adapter.available():
                continue
            try:
                combined.extend(adapter.search(str(query), limit=limit_per_source))
            except Exception:
                # Optional public knowledge can degrade without taking Mary down.
                continue
        seen: set[tuple[str, str]] = set()
        output: list[dict[str, Any]] = []
        for item in combined:
            key = (item.source, item.identifier or item.url or item.title)
            if key in seen:
                continue
            seen.add(key)
            output.append(item.to_dict())
        return output

    def status(self) -> dict[str, Any]:
        return {
            "version": self.VERSION,
            "authority": "external_evidence_only",
            "startup_network_dependency": False,
            "adapters": [
                {"name": adapter.name, "category": adapter.category, "available": adapter.available(), "requires_key": adapter.requires_key}
                for adapter in self.adapters
            ],
        }
