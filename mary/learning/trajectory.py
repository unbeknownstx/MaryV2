"""Content-free trajectory telemetry for MaryV2 evaluation and offline learning."""
from __future__ import annotations

from dataclasses import asdict, dataclass, field
from statistics import mean
from threading import RLock
from typing import Any
from uuid import uuid4


def _clamp(value: float, low: float, high: float) -> float:
    try:
        number = float(value)
    except (TypeError, ValueError):
        number = low
    return max(low, min(high, number))


@dataclass(frozen=True)
class TrajectorySample:
    trajectory_id: str
    task_class: str
    strategy: str
    passes: int
    branches: int
    verifier_score: float | None
    outcome: str
    reward: float | None
    provider_attempts: int
    tool_calls: int
    latency_ms: float
    total_tokens: int
    failure_kind: str | None = None
    tags: tuple[str, ...] = field(default_factory=tuple)

    def to_dict(self) -> dict[str, Any]:
        payload = asdict(self)
        payload["tags"] = list(self.tags)
        return payload


class TrajectoryRecorder:
    """Bounded structural evidence store; never stores prompts or responses."""

    VERSION = "13.31"

    def __init__(self, *, capacity: int = 256) -> None:
        self.capacity = max(16, min(5000, int(capacity)))
        self._samples: list[TrajectorySample] = []
        self._lock = RLock()

    def record(
        self,
        *,
        task_class: str,
        strategy: str,
        passes: int = 1,
        branches: int = 1,
        verifier_score: float | None = None,
        outcome: str = "unknown",
        reward: float | None = None,
        provider_attempts: int = 1,
        tool_calls: int = 0,
        latency_ms: float = 0.0,
        total_tokens: int = 0,
        failure_kind: str | None = None,
        tags: tuple[str, ...] | list[str] = (),
    ) -> TrajectorySample:
        score = None if verifier_score is None else _clamp(verifier_score, 0.0, 1.0)
        bounded_reward = None if reward is None else _clamp(reward, -1.0, 1.0)
        sample = TrajectorySample(
            trajectory_id=f"traj_{uuid4().hex[:20]}",
            task_class=str(task_class or "unknown")[:80],
            strategy=str(strategy or "single_pass")[:80],
            passes=max(1, min(16, int(passes))),
            branches=max(1, min(8, int(branches))),
            verifier_score=score,
            outcome=str(outcome or "unknown")[:40],
            reward=bounded_reward,
            provider_attempts=max(0, min(32, int(provider_attempts))),
            tool_calls=max(0, min(64, int(tool_calls))),
            latency_ms=round(max(0.0, min(float(latency_ms or 0.0), 86_400_000.0)), 2),
            total_tokens=max(0, min(int(total_tokens or 0), 50_000_000)),
            failure_kind=(None if not failure_kind else str(failure_kind)[:80]),
            tags=tuple(str(item)[:48] for item in list(tags)[:12]),
        )
        with self._lock:
            self._samples.append(sample)
            if len(self._samples) > self.capacity:
                del self._samples[: len(self._samples) - self.capacity]
        return sample

    def samples(self) -> list[dict[str, Any]]:
        with self._lock:
            return [item.to_dict() for item in self._samples]

    def snapshot(self) -> dict[str, Any]:
        with self._lock:
            samples = list(self._samples)
        successes = sum(1 for item in samples if item.outcome == "success")
        scored = [item.verifier_score for item in samples if item.verifier_score is not None]
        rewards = [item.reward for item in samples if item.reward is not None]
        return {
            "version": self.VERSION,
            "capacity": self.capacity,
            "sample_count": len(samples),
            "success_rate": (round(successes / len(samples), 4) if samples else None),
            "mean_verifier_score": (round(mean(scored), 4) if scored else None),
            "mean_reward": (round(mean(rewards), 4) if rewards else None),
            "content_retained": False,
            "automatic_training": False,
            "automatic_prompt_mutation": False,
            "authority": "evaluation_evidence_only",
        }
