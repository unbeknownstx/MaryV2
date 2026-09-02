"""Context-sensitive reranking for Mary's rebuildable cognitive reservoir.

This module never changes canonical memory.  It only adjusts the order of
already-retrieved candidates using bounded situational signals such as current
project/activity, episodic importance, and recency.
"""
from __future__ import annotations

from dataclasses import replace
from datetime import datetime, timezone
import math
from typing import Any, Mapping

from .reservoir import ReservoirHit


def _terms(value: Any) -> set[str]:
    text = "".join(
        ch.casefold() if ch.isalnum() or ch in "_-" else " "
        for ch in str(value or "")
    )
    stop = {"the", "and", "for", "with", "from", "this", "that", "mary", "creator"}
    return {token for token in text.split() if len(token) > 2 and token not in stop}


def _parse_time(value: Any) -> float | None:
    if isinstance(value, (int, float)):
        return float(value)
    text = str(value or "").strip()
    if not text:
        return None
    try:
        return datetime.fromisoformat(text.replace("Z", "+00:00")).timestamp()
    except Exception:
        return None


class ContextualReservoirReranker:
    VERSION = "2"

    def __init__(self) -> None:
        self.last_diagnostics: dict[str, dict[str, float]] = {}

    def rerank(
        self,
        hits: list[ReservoirHit],
        *,
        context: Mapping[str, Any] | None = None,
        limit: int | None = None,
    ) -> list[ReservoirHit]:
        if not hits or not isinstance(context, Mapping):
            return hits[:limit] if limit is not None else list(hits)

        workspace = context.get("workspace")
        if not isinstance(workspace, Mapping):
            workspace = context
        scene = workspace.get("live_scene") if isinstance(workspace, Mapping) else {}
        scene = scene if isinstance(scene, Mapping) else {}

        scene_terms: set[str] = set()
        for key in ("project", "activity", "workspace", "selected_asset", "mary_target", "mary_goal"):
            scene_terms |= _terms(scene.get(key))
        for event in list(scene.get("recent_events") or [])[:4]:
            if isinstance(event, Mapping):
                scene_terms |= _terms(event.get("summary"))

        now = datetime.now(timezone.utc).timestamp()
        output: list[ReservoirHit] = []
        diagnostics: dict[str, dict[str, float]] = {}
        for hit in hits:
            metadata = dict(hit.metadata or {})
            content_terms = _terms(
                f"{hit.subject} {hit.predicate} {hit.content} "
                f"{metadata.get('event_type', '')} {metadata.get('category', '')}"
            )
            overlap = 0.0
            if scene_terms:
                overlap = len(scene_terms & content_terms) / max(1, min(len(scene_terms), 8))
                overlap = max(0.0, min(1.0, overlap))

            try:
                importance = max(0.0, min(1.0, float(metadata.get("importance", 0.0) or 0.0)))
            except (TypeError, ValueError):
                importance = 0.0

            timestamp = _parse_time(metadata.get("timestamp"))
            recency = 0.0
            if timestamp is not None:
                age_days = max(0.0, (now - timestamp) / 86400.0)
                # Soft 30-day half-ish life; old memories remain retrievable,
                # they simply lose the small recency bonus.
                recency = math.exp(-age_days / 30.0)

            base = max(0.0, min(1.0, float(hit.score)))
            bonus = overlap * 0.14 + importance * 0.06 + recency * 0.04
            score = max(0.0, min(1.0, base + bonus))
            diagnostics[hit.record_id] = {
                "scene_relevance": round(overlap, 4),
                "importance": round(importance, 4),
                "recency": round(recency, 4),
                "bonus": round(bonus, 4),
            }
            # Context changes ordering only.  The authority-bearing hit payload,
            # especially metadata, must remain byte-for-byte identical to the
            # rebuildable selector record so canonical owner confirmation keeps
            # failing closed against stale or forged cache content.
            output.append(replace(hit, score=score))

        self.last_diagnostics = diagnostics
        output.sort(key=lambda item: (item.score, item.confidence), reverse=True)
        return output[:limit] if limit is not None else output
