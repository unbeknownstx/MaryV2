"""Proposal-only reasoning strategy advice from content-free trajectory evidence."""
from __future__ import annotations

from dataclasses import asdict, dataclass
from statistics import mean
from typing import Any, Iterable


@dataclass(frozen=True)
class StrategyProposal:
    task_class: str
    strategy: str | None
    sample_count: int
    utility: float | None
    confidence: float
    reason: str
    authority: str = "proposal_only_no_runtime_mutation"

    def to_dict(self) -> dict[str, Any]:
        return asdict(self)


class StrategyAdvisor:
    """Rank observed strategies conservatively; never changes Mary by itself."""

    VERSION = "13.33"
    VALID = {"single_pass", "verify_once", "branch_verify"}

    def __init__(self, *, min_samples: int = 5, min_margin: float = 0.06) -> None:
        self.min_samples = max(3, min(100, int(min_samples)))
        self.min_margin = max(0.01, min(0.5, float(min_margin)))

    @staticmethod
    def _utility(rows: list[dict[str, Any]]) -> float:
        successes = sum(1 for row in rows if str(row.get("outcome")) == "success")
        success_rate = (successes + 1.0) / (len(rows) + 2.0)
        rewards = [float(row["reward"]) for row in rows if row.get("reward") is not None]
        verifier = [float(row["verifier_score"]) for row in rows if row.get("verifier_score") is not None]
        reward_term = ((mean(rewards) + 1.0) / 2.0) if rewards else 0.5
        verifier_term = mean(verifier) if verifier else 0.5
        return round(0.70 * success_rate + 0.15 * reward_term + 0.15 * verifier_term, 4)

    def propose(self, samples: Iterable[dict[str, Any]], *, task_class: str) -> StrategyProposal:
        task = str(task_class or "general")[:80]
        matching = [
            dict(row)
            for row in samples
            if isinstance(row, dict) and str(row.get("task_class") or "") == task
        ]
        grouped: dict[str, list[dict[str, Any]]] = {}
        for row in matching:
            strategy = str(row.get("strategy") or "")
            if strategy in self.VALID:
                grouped.setdefault(strategy, []).append(row)

        eligible = {
            strategy: rows
            for strategy, rows in grouped.items()
            if len(rows) >= self.min_samples
        }
        if not eligible:
            return StrategyProposal(
                task_class=task,
                strategy=None,
                sample_count=len(matching),
                utility=None,
                confidence=0.0,
                reason="insufficient_structural_evidence",
            )

        ranked = sorted(
            ((self._utility(rows), strategy, len(rows)) for strategy, rows in eligible.items()),
            reverse=True,
        )
        best_utility, best_strategy, best_count = ranked[0]
        second_utility = ranked[1][0] if len(ranked) > 1 else 0.0
        margin = best_utility - second_utility
        if len(ranked) > 1 and margin < self.min_margin:
            return StrategyProposal(
                task_class=task,
                strategy=None,
                sample_count=sum(len(rows) for rows in eligible.values()),
                utility=best_utility,
                confidence=round(max(0.0, margin), 4),
                reason="evidence_margin_too_small",
            )
        confidence = min(0.95, 0.50 + min(best_count, 50) / 100.0 + max(0.0, margin) / 2.0)
        return StrategyProposal(
            task_class=task,
            strategy=best_strategy,
            sample_count=best_count,
            utility=best_utility,
            confidence=round(confidence, 4),
            reason="best_observed_structural_strategy",
        )

    def status(self) -> dict[str, Any]:
        return {
            "version": self.VERSION,
            "min_samples": self.min_samples,
            "min_margin": self.min_margin,
            "automatic_training": False,
            "automatic_policy_mutation": False,
            "content_required": False,
            "authority": "proposal_only_no_runtime_mutation",
        }
