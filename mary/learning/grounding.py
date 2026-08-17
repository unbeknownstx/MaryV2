"""
MaryV2 - Research Grounding

Deterministic source-grounding helpers for externally retrieved information.

This module does not browse the web and does not permanently store knowledge.
It ranks already-approved research sources so Mary's reasoning can distinguish
stronger evidence from weaker or stale snippets.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from datetime import datetime, timezone
import re
from typing import Any, Iterable
from urllib.parse import urlparse

from mary.learning.researcher import ResearchSource


@dataclass
class GroundingAssessment:
    """Grounding metadata for one research source."""

    source_id: str
    domain: str
    authority: float
    recency: float
    search_score: float
    resolution_score: float
    overall: float
    primary_source: bool = False
    observed_date: str | None = None
    stale_for_dynamic_query: bool = False
    reasons: list[str] = field(default_factory=list)

    def to_dict(self) -> dict[str, Any]:
        return {
            "source_id": self.source_id,
            "domain": self.domain,
            "authority": self.authority,
            "recency": self.recency,
            "search_score": self.search_score,
            "resolution_score": self.resolution_score,
            "overall": self.overall,
            "primary_source": self.primary_source,
            "observed_date": self.observed_date,
            "stale_for_dynamic_query": self.stale_for_dynamic_query,
            "reasons": list(self.reasons),
        }


class ResearchGrounder:
    """
    Rank externally retrieved sources before they reach Mary's reasoning.

    The grounder deliberately stays provider-agnostic. It consumes
    ResearchSource objects and uses only source metadata, URL/domain signals,
    search relevance, and visible date evidence. It does not pretend that a
    search snippet proves more than it actually contains.
    """

    DYNAMIC_MARKERS = {
        "latest",
        "current",
        "today",
        "recent",
        "news",
        "newest",
        "right now",
        "this week",
        "this month",
        "release",
        "version",
        "price",
        "prices",
        "weather",
    }

    OFFICIAL_PATH_MARKERS = (
        "/docs/",
        "/documentation/",
        "/developers/",
        "/developer/",
        "/reference/",
        "/api/",
        "/releases/",
        "/release/",
    )

    PRIMARY_TITLE_MARKERS = (
        "official",
        "documentation",
        "docs",
        "release notes",
        "releases",
        "changelog",
        "specification",
        "reference",
    )

    def rank_sources(
        self,
        query: str,
        sources: Iterable[ResearchSource],
        *,
        now: datetime | None = None,
    ) -> list[tuple[ResearchSource, GroundingAssessment]]:
        """Return sources ordered from strongest to weakest grounding."""

        current = now or datetime.now(timezone.utc)
        dynamic = self._is_dynamic_query(query)

        ranked: list[tuple[ResearchSource, GroundingAssessment]] = []
        for source in sources:
            assessment = self.assess_source(
                query,
                source,
                now=current,
                dynamic=dynamic,
            )
            ranked.append((source, assessment))

        ranked.sort(
            key=lambda pair: (
                pair[1].overall,
                pair[1].search_score,
                pair[1].authority,
            ),
            reverse=True,
        )
        return ranked

    def assess_source(
        self,
        query: str,
        source: ResearchSource,
        *,
        now: datetime | None = None,
        dynamic: bool | None = None,
    ) -> GroundingAssessment:
        current = now or datetime.now(timezone.utc)
        if dynamic is None:
            dynamic = self._is_dynamic_query(query)

        domain = self._domain(source.url)
        primary = self._looks_primary(source, domain)
        authority, authority_reasons = self._authority_score(
            source,
            domain,
            primary,
        )

        observed = self._observed_date(source)
        recency, stale, recency_reasons = self._recency_score(
            observed,
            now=current,
            dynamic=dynamic,
        )

        search_score = self._search_score(source)
        resolution_score = self._resolution_score(source)

        # Search relevance matters, but authority remains the largest signal.
        # SourceResolver contributes a bounded specificity/content-quality score
        # from the already-approved result set; it does not perform new access.
        if dynamic:
            overall = (
                authority * 0.40
                + recency * 0.30
                + search_score * 0.15
                + resolution_score * 0.15
            )
        else:
            overall = (
                authority * 0.50
                + recency * 0.10
                + search_score * 0.20
                + resolution_score * 0.20
            )

        reasons = authority_reasons + recency_reasons
        if search_score >= 0.75:
            reasons.append("high search relevance")
        elif search_score < 0.4:
            reasons.append("low search relevance")

        assessment = GroundingAssessment(
            source_id=source.id,
            domain=domain,
            authority=_clamp(authority),
            recency=_clamp(recency),
            search_score=_clamp(search_score),
            resolution_score=_clamp(resolution_score),
            overall=_clamp(overall),
            primary_source=primary,
            observed_date=(
                observed.date().isoformat()
                if observed is not None
                else None
            ),
            stale_for_dynamic_query=stale,
            reasons=reasons,
        )

        # Feed the grounded score into the existing Evaluator without coupling
        # Evaluator to any concrete search provider.
        source.confidence = assessment.overall
        source.metadata = dict(source.metadata)
        source.metadata["grounding"] = assessment.to_dict()

        return assessment

    def _authority_score(
        self,
        source: ResearchSource,
        domain: str,
        primary: bool,
    ) -> tuple[float, list[str]]:
        reasons: list[str] = []
        source_type = str(source.source_type or "web").lower()

        if domain.endswith(".gov") or ".gov." in domain:
            score = 0.95
            reasons.append("government domain")
        elif domain.endswith(".edu") or ".edu." in domain:
            score = 0.88
            reasons.append("academic domain")
        elif source_type in {
            "official",
            "documentation",
            "government",
            "academic",
            "research",
        }:
            score = 0.88
            reasons.append(f"trusted source type: {source_type}")
        elif primary:
            score = 0.82
            reasons.append("primary/official-source signals")
        else:
            score = 0.55
            reasons.append("general web source")

        # Provider search scores are relevance signals, not authority signals,
        # so they never promote an unknown domain to "official" on their own.
        return score, reasons

    def _looks_primary(
        self,
        source: ResearchSource,
        domain: str,
    ) -> bool:
        if not domain:
            return False

        url = str(source.url or "").lower()
        title = str(source.title or "").lower()
        source_type = str(source.source_type or "").lower()

        if source_type in {
            "official",
            "documentation",
            "government",
            "academic",
            "research",
        }:
            return True

        metadata = source.metadata if isinstance(source.metadata, dict) else {}
        resolution = metadata.get("source_resolution")
        if isinstance(resolution, dict):
            entity_match = _number(
                resolution.get("entity_domain_match"),
                0.0,
            )
            specificity = _number(
                resolution.get("specificity"),
                0.0,
            )
            generic_index = bool(
                resolution.get("generic_index", False)
            )
            if entity_match >= 0.95 and specificity >= 0.70 and not generic_index:
                return True

        if any(marker in url for marker in self.OFFICIAL_PATH_MARKERS):
            return True

        if any(marker in title for marker in self.PRIMARY_TITLE_MARKERS):
            return True

        if domain.startswith("docs.") or domain.startswith("developer."):
            return True

        return False

    def _recency_score(
        self,
        observed: datetime | None,
        *,
        now: datetime,
        dynamic: bool,
    ) -> tuple[float, bool, list[str]]:
        if observed is None:
            return (
                (0.45 if dynamic else 0.65),
                False,
                ["no publication/event date visible in search evidence"],
            )

        if observed.tzinfo is None:
            observed = observed.replace(tzinfo=timezone.utc)

        age_days = max((now - observed).days, 0)

        if age_days <= 30:
            score = 1.0
        elif age_days <= 90:
            score = 0.9
        elif age_days <= 180:
            score = 0.78
        elif age_days <= 365:
            score = 0.62
        elif age_days <= 730:
            score = 0.38
        else:
            score = 0.22

        stale = bool(dynamic and age_days > 365)
        reasons = [f"visible date is approximately {age_days} days old"]
        if stale:
            reasons.append("stale for a current/latest request")

        return score, stale, reasons

    def _observed_date(
        self,
        source: ResearchSource,
    ) -> datetime | None:
        metadata = source.metadata if isinstance(source.metadata, dict) else {}

        for key in (
            "published_date",
            "published_at",
            "date",
            "publication_date",
        ):
            parsed = _parse_date(metadata.get(key))
            if parsed is not None:
                return parsed

        visible = " ".join(
            part
            for part in (source.title, source.content)
            if part
        )
        return _extract_visible_date(visible)

    def _search_score(self, source: ResearchSource) -> float:
        metadata = source.metadata if isinstance(source.metadata, dict) else {}
        raw = metadata.get("score")
        try:
            if raw is not None:
                return _clamp(float(raw))
        except (TypeError, ValueError):
            pass

        # Preserve Researcher's own relevance estimate as a fallback.
        return _clamp(source.relevance)

    def _resolution_score(self, source: ResearchSource) -> float:
        metadata = source.metadata if isinstance(source.metadata, dict) else {}
        resolution = metadata.get("source_resolution")
        if not isinstance(resolution, dict):
            # Neutral default preserves behavior for sources that did not pass
            # through SourceResolver (including older tests and stored data).
            return 0.5
        return _clamp(
            _number(
                resolution.get("resolution_score"),
                0.5,
            )
        )

    def _is_dynamic_query(self, query: str) -> bool:
        lowered = str(query or "").lower()
        return any(marker in lowered for marker in self.DYNAMIC_MARKERS)

    @staticmethod
    def _domain(url: str) -> str:
        try:
            host = urlparse(str(url or "")).hostname or ""
        except ValueError:
            host = ""
        host = host.lower().strip(".")
        if host.startswith("www."):
            host = host[4:]
        return host


def _parse_date(value: Any) -> datetime | None:
    if value is None:
        return None

    text = str(value).strip()
    if not text:
        return None

    try:
        parsed = datetime.fromisoformat(text.replace("Z", "+00:00"))
        if parsed.tzinfo is None:
            parsed = parsed.replace(tzinfo=timezone.utc)
        return parsed.astimezone(timezone.utc)
    except ValueError:
        pass

    for fmt in (
        "%Y-%m-%d",
        "%Y/%m/%d",
        "%b %d, %Y",
        "%B %d, %Y",
        "%b %d %Y",
        "%B %d %Y",
    ):
        try:
            return datetime.strptime(text, fmt).replace(tzinfo=timezone.utc)
        except ValueError:
            continue

    return None


def _extract_visible_date(text: str) -> datetime | None:
    if not text:
        return None

    patterns = (
        r"\b(20\d{2}-\d{1,2}-\d{1,2})\b",
        r"\b((?:Jan(?:uary)?|Feb(?:ruary)?|Mar(?:ch)?|Apr(?:il)?|May|Jun(?:e)?|Jul(?:y)?|Aug(?:ust)?|Sep(?:tember)?|Oct(?:ober)?|Nov(?:ember)?|Dec(?:ember)?)\s+\d{1,2},?\s+20\d{2})\b",
    )

    for pattern in patterns:
        match = re.search(pattern, text, flags=re.IGNORECASE)
        if not match:
            continue
        parsed = _parse_date(match.group(1).replace(",", ","))
        if parsed is not None:
            return parsed

    return None


def _number(value: Any, default: float = 0.0) -> float:
    try:
        return float(value)
    except (TypeError, ValueError):
        return float(default)


def _clamp(value: float) -> float:
    return max(0.0, min(float(value), 1.0))
