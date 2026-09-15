"""Adaptive, content-free deliberation policy and bounded execution for MaryV2.

The governor selects how much *process* a turn deserves without exposing or
persisting private chain-of-thought. The executor applies that policy to opaque
candidate/verification callbacks. Candidate text is ephemeral working data;
telemetry receives structural metrics only.
"""
from __future__ import annotations

from dataclasses import asdict, dataclass, field
from time import monotonic
from typing import Any, Callable


def _clamp(value: float, low: float, high: float) -> float:
    try:
        number = float(value)
    except (TypeError, ValueError):
        number = low
    return max(low, min(high, number))


@dataclass(frozen=True)
class DeliberationPlan:
    strategy: str
    max_passes: int
    max_branches: int
    verifier_required: bool
    confidence_floor: float
    latency_budget_ms: int
    external_verifier_allowed: bool
    workspace_fields: tuple[str, ...] = (
        "facts",
        "constraints",
        "unknowns",
        "candidate_actions",
        "confidence",
    )
    persistence: str = "ephemeral_structural_state_only"
    expose_private_reasoning: bool = False
    authority: str = "cognition_policy_only"

    def to_dict(self) -> dict[str, Any]:
        payload = asdict(self)
        payload["workspace_fields"] = list(self.workspace_fields)
        return payload


@dataclass(frozen=True)
class DeliberationCandidate:
    """Opaque candidate answer used only inside one deliberation execution."""

    content: str
    confidence: float = 0.5
    structural_metrics: dict[str, int] = field(default_factory=dict)


@dataclass(frozen=True)
class VerificationResult:
    """Bounded verifier output. Feedback must be concise and non-CoT."""

    score: float
    accepted: bool | None = None
    issue_codes: tuple[str, ...] = field(default_factory=tuple)

    def bounded(self) -> "VerificationResult":
        return VerificationResult(
            score=_clamp(self.score, 0.0, 1.0),
            accepted=self.accepted,
            issue_codes=tuple(str(item)[:48] for item in self.issue_codes[:8]),
        )


@dataclass(frozen=True)
class DeliberationOutcome:
    content: str
    confidence: float
    strategy: str
    passes: int
    branches: int
    verifier_calls: int
    verifier_score: float | None
    degraded: bool
    failure_kind: str | None
    latency_ms: float
    authority: str = "bounded_cognitive_execution"
    private_reasoning_retained: bool = False

    def to_dict(self) -> dict[str, Any]:
        return asdict(self)


CandidateFactory = Callable[
    [int, int, DeliberationCandidate | None, VerificationResult | None],
    DeliberationCandidate,
]
Verifier = Callable[[DeliberationCandidate, int], VerificationResult]


class DeliberationGovernor:
    """Choose bounded test-time compute from an existing cognitive plan."""

    VERSION = "13.33"

    def __init__(
        self,
        *,
        max_passes: int = 4,
        max_branches: int = 3,
        default_confidence_floor: float = 0.78,
    ) -> None:
        self.max_passes = max(1, min(8, int(max_passes)))
        self.max_branches = max(1, min(4, int(max_branches)))
        self.default_confidence_floor = _clamp(
            default_confidence_floor, 0.50, 0.99
        )

    def plan(
        self,
        cognitive_plan: dict[str, Any] | None,
        *,
        uncertainty: float | None = None,
        verifier_available: bool = True,
        external_verifier_authorized: bool = False,
        realtime: bool = False,
    ) -> DeliberationPlan:
        plan = dict(cognitive_plan or {})
        mode = str(plan.get("cognitive_mode") or "balanced").strip().lower()
        depth = str(plan.get("reasoning_depth") or "moderate").strip().lower()
        latency = str(plan.get("latency_priority") or "responsive").strip().lower()

        if uncertainty is None:
            uncertainty = {
                "light": 0.18,
                "moderate": 0.34,
                "deep": 0.52,
            }.get(depth, 0.34)
        uncertainty = _clamp(uncertainty, 0.0, 1.0)

        if mode in {"direct", "relational"} and depth != "deep":
            strategy = "single_pass"
            passes = 1
            branches = 1
            verifier_required = False
        elif mode == "deliberate" or depth == "deep":
            if verifier_available and uncertainty >= 0.45:
                strategy = "branch_verify"
                passes = 3
                branches = 2
                verifier_required = True
            elif verifier_available:
                strategy = "verify_once"
                passes = 2
                branches = 1
                verifier_required = True
            else:
                strategy = "single_pass"
                passes = 1
                branches = 1
                verifier_required = False
        else:
            if verifier_available and uncertainty >= 0.50:
                strategy = "verify_once"
                passes = 2
                branches = 1
                verifier_required = True
            else:
                strategy = "single_pass"
                passes = 1
                branches = 1
                verifier_required = False

        passes = min(self.max_passes, passes)
        branches = min(self.max_branches, branches)

        budget = {
            "fast": 1800,
            "responsive": 4000,
            "quality_first": 12000,
        }.get(latency, 5000)
        if realtime:
            budget = min(budget, 3200)
            if strategy == "branch_verify":
                strategy = "verify_once"
                branches = 1
                passes = min(passes, 2)

        confidence_floor = self.default_confidence_floor
        if mode == "deliberate":
            confidence_floor = max(confidence_floor, 0.84)
        elif mode == "direct":
            confidence_floor = min(confidence_floor, 0.74)

        return DeliberationPlan(
            strategy=strategy,
            max_passes=passes,
            max_branches=branches,
            verifier_required=verifier_required,
            confidence_floor=round(confidence_floor, 3),
            latency_budget_ms=budget,
            external_verifier_allowed=bool(external_verifier_authorized),
        )

    def status(self) -> dict[str, Any]:
        return {
            "version": self.VERSION,
            "max_passes": self.max_passes,
            "max_branches": self.max_branches,
            "default_confidence_floor": self.default_confidence_floor,
            "private_reasoning_persistence": False,
            "private_reasoning_exposure": False,
            "automatic_training": False,
            "bounded_execution_available": True,
            "authority": "cognition_policy_only",
        }


class DeliberationExecutor:
    """Execute a DeliberationPlan without retaining intermediate reasoning text.

    The executor knows nothing about provider routing, identity, memory, or tool
    authorization. Callers supply candidate/verifier callbacks that already obey
    those owners. Only the winning candidate leaves this method.
    """

    VERSION = "13.33"

    def __init__(self, *, recorder: Any | None = None) -> None:
        self.recorder = recorder

    @staticmethod
    def _metric(candidate: DeliberationCandidate, key: str) -> int:
        try:
            return max(0, int(candidate.structural_metrics.get(key, 0)))
        except (TypeError, ValueError, AttributeError):
            return 0

    def execute(
        self,
        plan: DeliberationPlan | dict[str, Any],
        *,
        generate: CandidateFactory,
        verify: Verifier | None = None,
        task_class: str = "general",
    ) -> DeliberationOutcome:
        if isinstance(plan, DeliberationPlan):
            payload = plan.to_dict()
        else:
            payload = dict(plan or {})

        strategy = str(payload.get("strategy") or "single_pass")
        max_passes = max(1, min(8, int(payload.get("max_passes") or 1)))
        max_branches = max(1, min(4, int(payload.get("max_branches") or 1)))
        confidence_floor = _clamp(payload.get("confidence_floor", 0.78), 0.0, 1.0)
        verifier_required = bool(payload.get("verifier_required", False))
        latency_budget_ms = max(1, min(120_000, int(payload.get("latency_budget_ms") or 5000)))

        started = monotonic()
        candidates: list[tuple[DeliberationCandidate, VerificationResult | None]] = []
        passes = 0
        verifier_calls = 0
        degraded = False
        failure_kind: str | None = None

        def elapsed_ms() -> float:
            return (monotonic() - started) * 1000.0

        def produce(
            pass_index: int,
            branch_index: int,
            previous: DeliberationCandidate | None = None,
            verification: VerificationResult | None = None,
        ) -> DeliberationCandidate:
            nonlocal passes
            candidate = generate(pass_index, branch_index, previous, verification)
            if not isinstance(candidate, DeliberationCandidate):
                raise TypeError("generate must return DeliberationCandidate")
            passes += 1
            return DeliberationCandidate(
                content=str(candidate.content),
                confidence=_clamp(candidate.confidence, 0.0, 1.0),
                structural_metrics=dict(candidate.structural_metrics or {}),
            )

        def check(candidate: DeliberationCandidate, branch_index: int) -> VerificationResult | None:
            nonlocal verifier_calls, degraded, failure_kind
            if verify is None:
                if verifier_required:
                    degraded = True
                    failure_kind = failure_kind or "verifier_unavailable"
                return None
            try:
                result = verify(candidate, branch_index)
                if not isinstance(result, VerificationResult):
                    raise TypeError("verify must return VerificationResult")
                verifier_calls += 1
                return result.bounded()
            except Exception:
                degraded = True
                failure_kind = failure_kind or "verifier_failed"
                return None

        if strategy == "branch_verify" and verify is not None:
            branch_count = min(max_branches, max_passes)
            for branch_index in range(branch_count):
                if elapsed_ms() >= latency_budget_ms and candidates:
                    degraded = True
                    failure_kind = failure_kind or "latency_budget"
                    break
                candidate = produce(passes, branch_index)
                verification = check(candidate, branch_index)
                candidates.append((candidate, verification))
        else:
            first = produce(0, 0)
            first_verification = check(first, 0) if strategy == "verify_once" else None
            candidates.append((first, first_verification))

            first_score = (
                first_verification.score
                if first_verification is not None
                else first.confidence
            )
            if (
                strategy == "verify_once"
                and first_score < confidence_floor
                and passes < max_passes
                and elapsed_ms() < latency_budget_ms
            ):
                revised = produce(1, 0, first, first_verification)
                revised_verification = check(revised, 0)
                candidates.append((revised, revised_verification))
            elif strategy == "branch_verify" and verify is None:
                degraded = True
                failure_kind = failure_kind or "verifier_unavailable"

        def rank(item: tuple[DeliberationCandidate, VerificationResult | None]) -> tuple[float, float]:
            candidate, verification = item
            score = verification.score if verification is not None else candidate.confidence
            return (score, candidate.confidence)

        winner, winner_verification = max(candidates, key=rank)
        verifier_score = winner_verification.score if winner_verification is not None else None
        latency_ms = round(elapsed_ms(), 2)

        provider_attempts = sum(self._metric(item[0], "provider_attempts") for item in candidates)
        tool_calls = sum(self._metric(item[0], "tool_calls") for item in candidates)
        total_tokens = sum(self._metric(item[0], "total_tokens") for item in candidates)
        recorder = self.recorder
        if recorder is not None and callable(getattr(recorder, "record", None)):
            recorder.record(
                task_class=task_class,
                strategy=strategy,
                passes=passes,
                branches=max(1, len(candidates) if strategy == "branch_verify" else 1),
                verifier_score=verifier_score,
                outcome="degraded" if degraded else "success",
                provider_attempts=provider_attempts,
                tool_calls=tool_calls,
                latency_ms=latency_ms,
                total_tokens=total_tokens,
                failure_kind=failure_kind,
                tags=("bounded_deliberation",),
            )

        return DeliberationOutcome(
            content=winner.content,
            confidence=winner.confidence,
            strategy=strategy,
            passes=passes,
            branches=max(1, len(candidates) if strategy == "branch_verify" else 1),
            verifier_calls=verifier_calls,
            verifier_score=verifier_score,
            degraded=degraded,
            failure_kind=failure_kind,
            latency_ms=latency_ms,
        )
