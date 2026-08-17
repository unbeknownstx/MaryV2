"""
MaryV2 - Source Resolver

Deterministically improves already-retrieved web research before grounding.

The resolver NEVER performs network access. It works only with sources that
were already returned by an approved web tool request.

Responsibilities:

    provider search results
        ↓
    canonicalize / deduplicate
        ↓
    identify direct pages vs category/index pages
        ↓
    identify query↔domain alignment signals
        ↓
    prefer richer extracted evidence
        ↓
    ResearchGrounder / Evaluator / EvidenceValidator

This keeps source resolution provider-independent and preserves Mary's tool
approval boundary.
"""

from __future__ import annotations

from dataclasses import dataclass, field
import re
from typing import Any, Iterable
from urllib.parse import parse_qsl, urlencode, urlparse, urlunparse

from mary.learning.researcher import ResearchSource


@dataclass
class SourceResolution:
    """Deterministic resolution metadata for one research source."""

    source_id: str
    canonical_url: str
    domain: str
    specificity: float
    content_quality: float
    entity_domain_match: float
    resolution_score: float
    generic_index: bool = False
    reasons: list[str] = field(default_factory=list)

    def to_dict(self) -> dict[str, Any]:
        return {
            "source_id": self.source_id,
            "canonical_url": self.canonical_url,
            "domain": self.domain,
            "specificity": self.specificity,
            "content_quality": self.content_quality,
            "entity_domain_match": self.entity_domain_match,
            "resolution_score": self.resolution_score,
            "generic_index": self.generic_index,
            "reasons": list(self.reasons),
        }


class SourceResolver:
    """
    Improve search-result quality without performing another network request.

    Search providers frequently return a mixture of direct articles, category
    pages, documentation indexes, and duplicate tracking URLs. This resolver
    normalizes that set so stronger evidence reaches ResearchGrounder first.
    """

    TRACKING_KEYS = {
        "gclid",
        "fbclid",
        "msclkid",
        "mc_cid",
        "mc_eid",
        "ref",
        "ref_src",
        "source",
    }

    TRACKING_PREFIXES = (
        "utm_",
    )

    GENERIC_SEGMENTS = {
        "category",
        "categories",
        "tag",
        "tags",
        "topic",
        "topics",
        "search",
        "archive",
        "archives",
    }

    GENERIC_TITLES = {
        "news",
        "blog",
        "documentation",
        "docs",
        "home",
        "latest news",
    }

    DIRECT_PATH_MARKERS = (
        "/article/",
        "/articles/",
        "/post/",
        "/posts/",
        "/blog/",
        "/release/",
        "/releases/",
        "/changelog/",
        "/announcement/",
        "/announcements/",
    )

    QUERY_STOPWORDS = {
        "a",
        "an",
        "and",
        "about",
        "for",
        "from",
        "in",
        "is",
        "it",
        "latest",
        "new",
        "news",
        "newest",
        "of",
        "on",
        "recent",
        "release",
        "releases",
        "the",
        "this",
        "today",
        "version",
        "what",
        "with",
    }

    def resolve(
        self,
        query: str,
        sources: Iterable[ResearchSource],
        *,
        max_sources: int = 10,
    ) -> list[ResearchSource]:
        """Return canonicalized, deduplicated, resolution-scored sources."""

        resolved_by_url: dict[str, ResearchSource] = {}
        url_order: list[str] = []

        for source in sources:
            if not isinstance(source, ResearchSource):
                continue

            assessment = self.assess_source(query, source)
            canonical = assessment.canonical_url or source.url

            source.url = canonical
            source.metadata = dict(source.metadata or {})
            source.metadata["source_resolution"] = assessment.to_dict()

            key = canonical or f"id:{source.id}"
            existing = resolved_by_url.get(key)

            if existing is None:
                resolved_by_url[key] = source
                url_order.append(key)
                continue

            if self._source_strength(source) > self._source_strength(existing):
                resolved_by_url[key] = source

        resolved = [resolved_by_url[key] for key in url_order]

        resolved.sort(
            key=lambda source: (
                self._resolution_score(source),
                self._provider_score(source),
                len(str(source.content or "")),
            ),
            reverse=True,
        )

        return resolved[: max(1, int(max_sources))]

    def assess_source(
        self,
        query: str,
        source: ResearchSource,
    ) -> SourceResolution:
        canonical = self.canonicalize_url(source.url)
        domain = self._domain(canonical)
        generic_index = self._looks_generic_index(source, canonical)
        specificity, specificity_reasons = self._specificity(
            source,
            canonical,
            generic_index,
        )
        content_quality, content_reasons = self._content_quality(source)
        entity_match, entity_reasons = self._entity_domain_match(query, domain)

        resolution_score = _clamp(
            specificity * 0.40
            + content_quality * 0.35
            + entity_match * 0.25
        )

        reasons = (
            specificity_reasons
            + content_reasons
            + entity_reasons
        )

        return SourceResolution(
            source_id=source.id,
            canonical_url=canonical,
            domain=domain,
            specificity=specificity,
            content_quality=content_quality,
            entity_domain_match=entity_match,
            resolution_score=resolution_score,
            generic_index=generic_index,
            reasons=reasons,
        )

    def canonicalize_url(self, url: str) -> str:
        """Remove fragments and common tracking parameters from a URL."""

        text = str(url or "").strip()
        if not text:
            return ""

        try:
            parsed = urlparse(text)
        except ValueError:
            return text

        if not parsed.scheme or not parsed.netloc:
            return text

        filtered_query: list[tuple[str, str]] = []
        for key, value in parse_qsl(parsed.query, keep_blank_values=True):
            lowered = key.lower()
            if lowered in self.TRACKING_KEYS:
                continue
            if any(lowered.startswith(prefix) for prefix in self.TRACKING_PREFIXES):
                continue
            filtered_query.append((key, value))

        path = parsed.path or "/"
        if path != "/":
            path = path.rstrip("/") or "/"

        return urlunparse(
            (
                parsed.scheme.lower(),
                parsed.netloc.lower(),
                path,
                parsed.params,
                urlencode(filtered_query, doseq=True),
                "",
            )
        )

    def _specificity(
        self,
        source: ResearchSource,
        canonical_url: str,
        generic_index: bool,
    ) -> tuple[float, list[str]]:
        reasons: list[str] = []

        try:
            path = urlparse(canonical_url).path.lower()
        except ValueError:
            path = ""

        segments = [segment for segment in path.split("/") if segment]

        if generic_index:
            score = 0.30
            reasons.append("category/index-style result")
        elif any(marker in path for marker in self.DIRECT_PATH_MARKERS):
            score = 0.95
            reasons.append("direct article/release path")
        elif len(segments) >= 3:
            score = 0.86
            reasons.append("deep, source-specific URL")
        elif len(segments) == 2:
            score = 0.72
            reasons.append("moderately specific URL")
        elif len(segments) == 1:
            score = 0.52
            reasons.append("broad one-segment URL")
        else:
            score = 0.35
            reasons.append("site root")

        title = str(source.title or "").strip().lower()
        if title and title not in self.GENERIC_TITLES and len(title.split()) >= 4:
            score = min(1.0, score + 0.08)
            reasons.append("descriptive result title")

        return _clamp(score), reasons

    def _content_quality(
        self,
        source: ResearchSource,
    ) -> tuple[float, list[str]]:
        content = re.sub(r"\s+", " ", str(source.content or "")).strip()
        length = len(content)
        metadata = source.metadata if isinstance(source.metadata, dict) else {}
        content_source = str(metadata.get("content_source", "")).lower()

        if length >= 4000:
            score = 1.0
        elif length >= 1800:
            score = 0.90
        elif length >= 800:
            score = 0.78
        elif length >= 300:
            score = 0.64
        elif length >= 100:
            score = 0.50
        else:
            score = 0.32

        reasons = [f"retrieved evidence contains {length} characters"]

        if content_source == "raw_content":
            score = min(1.0, score + 0.08)
            reasons.append("provider supplied extracted page content")
        elif content_source == "snippet":
            reasons.append("provider supplied search snippet only")

        return _clamp(score), reasons

    def _entity_domain_match(
        self,
        query: str,
        domain: str,
    ) -> tuple[float, list[str]]:
        if not domain:
            return 0.0, ["no domain available"]

        query_tokens = {
            token
            for token in re.findall(r"[a-z0-9]+", str(query or "").lower())
            if len(token) >= 3 and token not in self.QUERY_STOPWORDS
        }

        base = self._base_domain_token(domain)
        if base and base in query_tokens:
            return 1.0, ["query entity aligns with source domain"]

        domain_tokens = {
            token
            for token in re.findall(r"[a-z0-9]+", domain.lower())
            if len(token) >= 3
        }

        if query_tokens & domain_tokens:
            return 0.72, ["query terminology overlaps source domain"]

        return 0.15, ["no direct query↔domain alignment signal"]

    def _looks_generic_index(
        self,
        source: ResearchSource,
        canonical_url: str,
    ) -> bool:
        try:
            parsed = urlparse(canonical_url)
            path = parsed.path.lower().strip("/")
        except ValueError:
            path = ""

        segments = [segment for segment in path.split("/") if segment]
        title = str(source.title or "").strip().lower()

        if not segments:
            return True

        if segments[0] in self.GENERIC_SEGMENTS:
            return True

        if any(segment in self.GENERIC_SEGMENTS for segment in segments[:-1]):
            return True

        if segments[-1] in {"index.html", "index.htm", "index"}:
            return True

        # Broad hub pages such as /python or /news are useful discovery
        # sources, but they should not outrank a direct dated article/release.
        if len(segments) == 1 and segments[0] in {
            "news",
            "python",
            "blog",
            "updates",
            "releases",
        }:
            return True

        if title in self.GENERIC_TITLES:
            return True

        return False

    def _source_strength(self, source: ResearchSource) -> tuple[float, float, int]:
        return (
            self._resolution_score(source),
            self._provider_score(source),
            len(str(source.content or "")),
        )

    @staticmethod
    def _resolution_score(source: ResearchSource) -> float:
        metadata = source.metadata if isinstance(source.metadata, dict) else {}
        resolution = metadata.get("source_resolution")
        if isinstance(resolution, dict):
            return _number(resolution.get("resolution_score"), 0.0)
        return 0.0

    @staticmethod
    def _provider_score(source: ResearchSource) -> float:
        metadata = source.metadata if isinstance(source.metadata, dict) else {}
        return _number(metadata.get("score"), source.relevance)

    @staticmethod
    def _domain(url: str) -> str:
        try:
            host = urlparse(str(url or "")).hostname or ""
        except ValueError:
            return ""
        host = host.lower().strip(".")
        if host.startswith("www."):
            host = host[4:]
        return host

    @staticmethod
    def _base_domain_token(domain: str) -> str:
        labels = [label for label in str(domain or "").lower().split(".") if label]
        if len(labels) < 2:
            return labels[0] if labels else ""

        # This intentionally stays lightweight and deterministic. It handles
        # common ccTLD shapes without introducing a public-suffix dependency.
        if len(labels) >= 3 and labels[-2] in {
            "co",
            "com",
            "org",
            "net",
            "gov",
            "ac",
        }:
            return labels[-3]

        return labels[-2]


def _number(value: Any, default: float = 0.0) -> float:
    try:
        return float(value)
    except (TypeError, ValueError):
        return float(default)


def _clamp(value: float) -> float:
    return max(0.0, min(float(value), 1.0))