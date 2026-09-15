"""Deterministic execution reliability primitives for Mary capability workers.

These helpers are deliberately below Mary's identity, memory and permission owners.
They improve execution quality without granting authority: callers still have to
pass the existing Core/device permission boundaries before anything can run.

The design is intentionally runtime-agnostic so Ollama, MCP, creator workers and
future capability nodes can share the same retry/progress/resource semantics.
"""
from __future__ import annotations

from collections import deque
from dataclasses import asdict, dataclass, field
from hashlib import sha256
from time import monotonic
from typing import Any, Iterable


VERSION = "13.37"

# Only failures that are plausibly transport/transient failures are retryable.
_TRANSIENT_MARKERS = (
    "timeout",
    "timed out",
    "temporarily unavailable",
    "temporarily_unavailable",
    "transport_error",
    "rate_limited",
    "busy",
    "connection reset",
    "connection refused",
    "econnrefused",
    "fetch failed",
    "service unavailable",
    "http 429",
    "http 502",
    "http 503",
    "http 504",
)


@dataclass(frozen=True)
class ExecutionBudget:
    """Per-run operational limits; never a permission grant."""

    max_attempts: int = 3
    max_elapsed_ms: float = 180_000.0
    max_failures: int = 6

    def normalized(self) -> "ExecutionBudget":
        return ExecutionBudget(
            max_attempts=max(1, min(20, int(self.max_attempts))),
            max_elapsed_ms=max(1_000.0, min(3_600_000.0, float(self.max_elapsed_ms))),
            max_failures=max(1, min(50, int(self.max_failures))),
        )


@dataclass(frozen=True)
class ReliabilityVerdict:
    action: str
    reason: str = ""
    message: str = ""

    def to_dict(self) -> dict[str, Any]:
        return asdict(self)


@dataclass(frozen=True)
class ExecutionEvidence:
    """Content-free execution evidence safe for operational telemetry."""

    capability: str
    operation: str
    success: bool
    elapsed_ms: float
    attempts: int = 1
    error_class: str = ""
    side_effect_key: str | None = None
    output_units: int | None = None
    measured_at_monotonic: float = field(default_factory=monotonic, repr=False)

    def to_dict(self) -> dict[str, Any]:
        values = asdict(self)
        values.pop("measured_at_monotonic", None)
        values["authority"] = "operational_hint_only"
        return values


def stable_args_fingerprint(args: dict[str, Any] | None) -> str:
    """Create a small deterministic identity without retaining argument content."""

    def _shape(value: Any) -> Any:
        if isinstance(value, dict):
            return {str(key): _shape(value[key]) for key in sorted(value)}
        if isinstance(value, (list, tuple)):
            return [_shape(item) for item in value]
        if value is None:
            return None
        # Preserve type + bounded primitive value for scheduling identity while
        # avoiding bulk payload retention (prompts/files/results never enter logs).
        if isinstance(value, bool):
            return value
        if isinstance(value, (int, float)):
            return value
        text = str(value)
        return {"type": type(value).__name__, "len": len(text), "head_hash": sha256(text[:64].encode("utf-8", "ignore")).hexdigest()[:12]}

    import json

    encoded = json.dumps(_shape(dict(args or {})), sort_keys=True, separators=(",", ":"), ensure_ascii=True)
    return sha256(encoded.encode("utf-8")).hexdigest()[:20]


def derive_side_effect_key(capability: str, args: dict[str, Any] | None = None) -> str | None:
    """Return a serialization key for shared mutable resources.

    ``None`` means no shared mutable resource is known and parallel execution is
    allowed by this layer. This function never authorizes execution.
    """

    name = str(capability or "").strip().lower()
    values = dict(args or {})

    if name in {"llm.ollama", "llm.llama_cpp"}:
        # A single local accelerator/runtime can become unstable when multiple
        # heavyweight loads race. Nodes may later refine this with GPU IDs.
        return f"inference:{name}"
    if name.startswith("mcp."):
        server = name.removeprefix("mcp.") or "unknown"
        tool = str(values.get("tool") or "unknown").strip().lower()[:96]
        # External MCP tools are conservatively serialized by server/tool. The
        # tool may be read-only, but Mary does not infer that from a name.
        return f"mcp:{server}:{tool}"
    if name in {"creator.image", "creator.video", "creative_workspace"}:
        return "accelerator:creator"
    if name.startswith("sensor."):
        # Capture/transcription do not mutate Mary state; keep them keyless.
        return None
    if name == "personal_search":
        return None
    return None


def transient_error(error: str | BaseException | None) -> bool:
    text = str(error or "").strip().lower()
    return bool(text) and any(marker in text for marker in _TRANSIENT_MARKERS)


def should_retry(
    *,
    attempt: int,
    budget: ExecutionBudget,
    error: str | BaseException | None,
    mutating: bool,
    cancelled: bool = False,
) -> bool:
    """Retry only bounded, non-mutating, transient failures.

    A mutating call may have succeeded before its transport failed, so replaying
    it blindly can duplicate the effect. Cancellation is user intent, not a
    transient error.
    """

    limits = budget.normalized()
    if cancelled or mutating:
        return False
    if int(attempt) >= limits.max_attempts:
        return False
    return transient_error(error)


class ProgressGuard:
    """Detect bounded execution stalls without inspecting private content.

    The guard operates on capability + argument fingerprints and outcome classes.
    Any successful mutation starts a new epoch because repeated reads may then
    legitimately return different results.
    """

    def __init__(
        self,
        *,
        window: int = 6,
        steer_repeat: int = 3,
        halt_repeat: int = 5,
        halt_failures: int = 6,
    ) -> None:
        self.window = max(3, min(20, int(window)))
        self.steer_repeat = max(2, int(steer_repeat))
        self.halt_repeat = max(self.steer_repeat + 1, int(halt_repeat))
        self.halt_failures = max(3, int(halt_failures))
        self._recent: deque[str] = deque(maxlen=self.window)
        self._counts: dict[str, int] = {}
        self._steered: set[str] = set()
        self._consecutive_failures = 0

    def reset_epoch(self) -> None:
        self._recent.clear()
        self._counts.clear()

    def before(self, capability: str, args: dict[str, Any] | None, *, mutating: bool = False) -> ReliabilityVerdict:
        signature = f"{str(capability).strip().lower()}:{stable_args_fingerprint(args)}"
        if mutating:
            # The call may change the world. Repetition before the mutation is
            # no longer evidence about repetition after it.
            self.reset_epoch()
            return ReliabilityVerdict("ok")

        self._recent.append(signature)
        count = self._counts.get(signature, 0) + 1
        self._counts[signature] = count
        window_count = sum(1 for item in self._recent if item == signature)

        if count >= self.halt_repeat or window_count >= self.halt_repeat:
            return ReliabilityVerdict(
                "halt",
                reason="repeated_identical_operation_without_progress",
                message="The same read-only operation is repeating without an intervening state change.",
            )
        if (count >= self.steer_repeat or window_count >= self.steer_repeat) and signature not in self._steered:
            self._steered.add(signature)
            return ReliabilityVerdict(
                "steer",
                reason="repeated_operation",
                message="Use the existing result or choose a materially different next action instead of repeating the same operation.",
            )
        return ReliabilityVerdict("ok")

    def after(self, *, success: bool, mutating: bool = False, error: str | BaseException | None = None) -> ReliabilityVerdict:
        if success:
            self._consecutive_failures = 0
            if mutating:
                self.reset_epoch()
            return ReliabilityVerdict("ok")

        self._consecutive_failures += 1
        if self._consecutive_failures >= self.halt_failures:
            return ReliabilityVerdict(
                "halt",
                reason="consecutive_failures_without_progress",
                message=f"{self._consecutive_failures} consecutive execution attempts failed; stop retrying the same strategy.",
            )
        if self._consecutive_failures == max(3, self.halt_failures // 2):
            return ReliabilityVerdict(
                "steer",
                reason="repeated_failures",
                message=(
                    "Several execution attempts failed without progress. Inspect the current error, "
                    "change strategy, switch capability/model, or finish with a bounded failure."
                ),
            )
        return ReliabilityVerdict("ok")


class ReliabilityLedger:
    """Bounded content-free rolling evidence; disposable on restart."""

    def __init__(self, *, max_entries: int = 200) -> None:
        self.max_entries = max(20, min(5_000, int(max_entries)))
        self._items: deque[ExecutionEvidence] = deque(maxlen=self.max_entries)

    def record(self, evidence: ExecutionEvidence) -> None:
        self._items.append(evidence)

    def snapshot(self) -> dict[str, Any]:
        return {
            "version": VERSION,
            "entries": [item.to_dict() for item in self._items],
            "authority": "operational_hint_only",
            "content_retained": False,
        }

    def success_rate(self, capability: str, operation: str = "") -> float | None:
        name = str(capability or "").strip().lower()
        op = str(operation or "").strip().lower()
        items = [
            item for item in self._items
            if item.capability.strip().lower() == name
            and (not op or item.operation.strip().lower() == op)
        ]
        if not items:
            return None
        return round(sum(1 for item in items if item.success) / len(items), 3)


def compact_error_class(error: str | BaseException | None) -> str:
    """Return a safe structural error label without persisting the error text."""

    if error is None:
        return ""
    if isinstance(error, BaseException):
        return type(error).__name__[:80]
    text = str(error).strip()
    if not text:
        return ""
    head = text.split(":", 1)[0].strip()
    return (head or "execution_error")[:80]


def any_halt(verdicts: Iterable[ReliabilityVerdict]) -> ReliabilityVerdict:
    items = list(verdicts)
    for item in items:
        if item.action == "halt":
            return item
    for item in items:
        if item.action == "steer":
            return item
    return ReliabilityVerdict("ok")
