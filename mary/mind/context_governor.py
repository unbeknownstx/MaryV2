"""Deterministic per-turn evidence/context governor for MaryV2.

Mary has multiple evidence owners with different authority semantics.  This
governor does *not* merge them into one score or truth store.  It only chooses
how many whole candidate records from each lane are allowed into a model-facing
working set.

The rules are deliberately simple:
- whole records are kept or dropped; factual fields are never paraphrased here;
- each lane has its own budget so a large knowledge pack cannot crowd out plans,
  world-state or procedural evidence;
- a total budget bounds the blackboard for small local models;
- authority remains attached to the lane that supplied the record;
- dropped records remain in their owning store and can be retrieved later.
"""
from __future__ import annotations

from dataclasses import dataclass
import json
from typing import Any, Iterable


@dataclass(frozen=True)
class ContextLaneReport:
    lane: str
    candidates: int
    kept: int
    dropped: int
    candidate_characters: int
    kept_characters: int
    lane_budget_characters: int

    def to_dict(self) -> dict[str, Any]:
        return {
            "lane": self.lane,
            "candidates": self.candidates,
            "kept": self.kept,
            "dropped": self.dropped,
            "candidate_characters": self.candidate_characters,
            "kept_characters": self.kept_characters,
            "lane_budget_characters": self.lane_budget_characters,
        }


class ContextEvidenceGovernor:
    """Bound model-facing evidence without becoming a retrieval authority."""

    VERSION = 1

    DEFAULT_LANE_BUDGETS = {
        "world": 2400,
        "skills": 3200,
        "plans": 2600,
        "knowledge": 4200,
        "compute": 2200,
    }

    def __init__(
        self,
        *,
        total_characters: int = 14_000,
        lane_budgets: dict[str, int] | None = None,
    ) -> None:
        self.total_characters = max(2000, min(100_000, int(total_characters)))
        raw = dict(self.DEFAULT_LANE_BUDGETS)
        raw.update(dict(lane_budgets or {}))
        self.lane_budgets = {
            str(lane): max(256, min(self.total_characters, int(limit)))
            for lane, limit in raw.items()
        }

    @staticmethod
    def _cost(item: Any) -> int:
        try:
            return len(
                json.dumps(
                    item,
                    ensure_ascii=False,
                    sort_keys=True,
                    separators=(",", ":"),
                    default=str,
                )
            )
        except Exception:
            return len(str(item))

    def govern_lane(
        self,
        lane: str,
        candidates: Iterable[dict[str, Any]],
        *,
        score_key: str | None = None,
        minimum_score: float | None = None,
        remaining_total: int | None = None,
    ) -> tuple[list[dict[str, Any]], ContextLaneReport]:
        name = str(lane or "general").strip().casefold()
        rows = [dict(item) for item in candidates if isinstance(item, dict)]
        if score_key:
            def score(row: dict[str, Any]) -> float:
                try:
                    return float(row.get(score_key, 0.0) or 0.0)
                except (TypeError, ValueError):
                    return 0.0
            rows.sort(key=score, reverse=True)
            if minimum_score is not None:
                rows = [row for row in rows if score(row) >= float(minimum_score)]

        lane_budget = int(self.lane_budgets.get(name, 1800))
        if remaining_total is not None:
            lane_budget = min(lane_budget, max(0, int(remaining_total)))

        candidate_chars = sum(self._cost(row) for row in rows)
        kept: list[dict[str, Any]] = []
        used = 0
        for row in rows:
            cost = self._cost(row)
            if cost > lane_budget:
                continue
            if used + cost > lane_budget:
                continue
            kept.append(row)
            used += cost

        report = ContextLaneReport(
            lane=name,
            candidates=len(rows),
            kept=len(kept),
            dropped=max(0, len(rows) - len(kept)),
            candidate_characters=candidate_chars,
            kept_characters=used,
            lane_budget_characters=lane_budget,
        )
        return kept, report

    def govern(
        self,
        lanes: dict[str, list[dict[str, Any]]],
        *,
        lane_rules: dict[str, dict[str, Any]] | None = None,
    ) -> tuple[dict[str, list[dict[str, Any]]], dict[str, Any]]:
        """Apply independent lane budgets plus one cumulative turn budget."""

        rules = dict(lane_rules or {})
        selected: dict[str, list[dict[str, Any]]] = {}
        reports: list[ContextLaneReport] = []
        remaining = self.total_characters
        # Authority-bearing operational lanes come before large reference text.
        order = ["world", "plans", "skills", "compute", "knowledge"]
        order.extend(name for name in lanes if name not in order)

        for lane in order:
            if lane not in lanes:
                continue
            rule = dict(rules.get(lane) or {})
            rows, report = self.govern_lane(
                lane,
                lanes[lane],
                score_key=rule.get("score_key"),
                minimum_score=rule.get("minimum_score"),
                remaining_total=remaining,
            )
            selected[lane] = rows
            reports.append(report)
            remaining = max(0, remaining - report.kept_characters)

        used = self.total_characters - remaining
        return selected, {
            "version": self.VERSION,
            "total_budget_characters": self.total_characters,
            "used_characters": used,
            "remaining_characters": remaining,
            "estimated_tokens_chars_div_4": round(used / 4.0, 1),
            "lanes": [report.to_dict() for report in reports],
            "semantics": (
                "whole candidate records only; candidates dropped for context "
                "budget remain available in their owning stores"
            ),
            "authority": "prompt-context budget only; no truth, memory or retrieval authority",
        }
