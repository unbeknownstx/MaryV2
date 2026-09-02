"""Bounded, content-free observability for one canonical Mary turn."""
from __future__ import annotations

from contextlib import contextmanager
from contextvars import ContextVar, Token
from dataclasses import dataclass, field
import hashlib
import json
import logging
import re
from threading import RLock
from time import monotonic
from typing import Any, Callable, Iterator
from uuid import uuid4


_STAGES = {
    "core_ingress",
    "authentication",
    "lifecycle_gate",
    "turn_lock_acquisition",
    "application_turn",
    "context_construction",
    "context_assembly",
    "character_sourcebook_retrieval",
    "sourcebook_projection",
    "memory_retrieval",
    "relationship_projection",
    "developed_self_projection",
    "provider_availability",
    "provider_routing",
    "provider_attempt",
    "provider_generation",
    "provider_fallback",
    "dialogue_realization",
    "dialogue_persistence",
    "experience_growth",
    "growth_processing",
    "preference_evidence",
    "memory_write",
    "memory_consolidation",
    "relationship_learning",
    "attention_publication",
    "attention_judgment",
    "peripheral_awareness",
    "cross_surface_awareness",
    "fast_brain",
    "speech_arbitration",
    "action_window",
    "autonomy_processing",
    "autonomy_evaluation",
    "autonomy_proposal",
    "persistence",
    "response_serialization",
    "serialization",
}
_STATUSES = {"success", "failure", "skipped"}
_TERMINAL_OUTCOMES = {"success", "failure", "replayed"}
_RESULT_ID_KEYS = {
    "experience_id", "preference_evidence_id", "preference_candidate_id",
    "developed_preference_id", "promotion_id", "memory_operation_id",
    "memory_object_id", "relationship_observation_id",
    "relationship_profile_id", "relationship_history_id", "attention_id",
    "autonomy_cycle_id", "autonomy_evaluation_id", "autonomy_proposal_id",
    "tool_request_id", "capability_request_id",
    "peripheral_note_id", "speech_request_id", "action_window_id",
    "action_selection_id",
}
_FAILURE_KINDS = {
    "application_exception",
    "authentication_failure",
    "invalid_request",
    "lock_failure",
    "post_processing_failure",
    "provider_error",
    "provider_exhausted",
    "provider_timeout",
    "serialization_failure",
    "upstream_disconnect",
    "unknown",
}
_SAFE_ID = re.compile(r"^[A-Za-z0-9][A-Za-z0-9_.:-]{0,127}$")
_SAFE_LABEL = re.compile(r"[^A-Za-z0-9_.:-]+")
_CURRENT: ContextVar["TurnTraceRecorder | None"] = ContextVar(
    "mary_turn_trace",
    default=None,
)

_LOGGER = logging.getLogger("mary.turn")
if not _LOGGER.handlers:
    _handler = logging.StreamHandler()
    _handler.setFormatter(logging.Formatter("%(message)s"))
    _LOGGER.addHandler(_handler)
_LOGGER.setLevel(logging.INFO)
_LOGGER.propagate = False


def bounded_identifier(value: Any, *, default_prefix: str = "request") -> str:
    """Return a log-safe correlation identifier without preserving arbitrary text."""

    cleaned = str(value or "").strip()
    if _SAFE_ID.fullmatch(cleaned):
        return cleaned
    return f"{default_prefix}_{uuid4().hex}"


def trace_correlation_id(value: Any, *, prefix: str) -> str:
    """Project caller-visible correlation values as non-reversible opaque IDs."""

    safe_prefix = bounded_type_name(prefix).lower()
    supplied = str(value or "").strip()
    if re.fullmatch(rf"{re.escape(safe_prefix)}_[0-9a-f]{{24}}", supplied):
        return supplied
    if not supplied:
        supplied = uuid4().hex
    digest = hashlib.sha256(supplied.encode("utf-8")).hexdigest()[:24]
    return f"{safe_prefix}_{digest}"


def safe_link_identifier(value: Any) -> str:
    """Return an existing opaque ID when it is safe to expose, else no ID."""

    cleaned = str(value or "").strip()
    return cleaned if _SAFE_ID.fullmatch(cleaned) else ""


def causal_operation_id(turn_id: Any, subsystem: str, operation: str) -> str:
    """Create one opaque ID at a real subsystem operation boundary."""

    del turn_id
    safe_subsystem = bounded_type_name(subsystem).lower()
    safe_operation = bounded_type_name(operation).lower()
    return f"{safe_subsystem}_{safe_operation}_{uuid4().hex[:24]}"


def upstream_request_hash(value: Any) -> str:
    """Return a non-reversible bounded correlation for an upstream request ID."""

    supplied = str(value or "").strip()
    if not supplied:
        return ""
    return hashlib.sha256(supplied.encode("utf-8")).hexdigest()[:24]


def bounded_type_name(value: Any) -> str:
    name = value if isinstance(value, str) else type(value).__name__
    return _SAFE_LABEL.sub("-", str(name or "unknown"))[:80] or "unknown"


def classify_failure(exc: BaseException | None, *, default: str = "unknown") -> str:
    """Classify failures without recording exception messages."""

    if exc is None:
        return default if default in _FAILURE_KINDS else "unknown"
    name = type(exc).__name__.lower()
    if isinstance(exc, TimeoutError) or "timeout" in name or "timedout" in name:
        return "provider_timeout"
    return default if default in _FAILURE_KINDS else "unknown"


@dataclass
class TurnTraceRecorder:
    """One bounded request trace safe for production logs."""

    request_id: str
    core_instance_id: str
    core_uptime_ms: Callable[[], float] | None = None
    sink: Callable[[dict[str, Any]], None] | None = None
    upstream_request_hash: str = ""
    max_stages: int = 64
    started: float = field(default_factory=monotonic)
    turn_id: str = ""
    conversation_id: str = ""
    replayed: bool = field(default=False, init=False)
    _stages: list[dict[str, Any]] = field(default_factory=list, init=False)
    _finished: bool = field(default=False, init=False)
    _completion: dict[str, Any] | None = field(default=None, init=False, repr=False)
    _dropped_stages: int = field(default=0, init=False)
    _lock: RLock = field(default_factory=RLock, init=False, repr=False)

    def __post_init__(self) -> None:
        self.request_id = trace_correlation_id(
            self.request_id,
            prefix="request",
        )
        self.core_instance_id = bounded_identifier(
            self.core_instance_id,
            default_prefix="core",
        )
        self.max_stages = max(16, min(128, int(self.max_stages)))
        self.upstream_request_hash = (
            str(self.upstream_request_hash or "")[:24]
            if re.fullmatch(r"[0-9a-f]{24}", str(self.upstream_request_hash or ""))
            else ""
        )

    def set_turn_id(self, value: Any) -> None:
        with self._lock:
            if not self._finished:
                self.turn_id = trace_correlation_id(value, prefix="turn")

    def set_conversation_id(self, value: Any) -> None:
        with self._lock:
            if not self._finished:
                self.conversation_id = trace_correlation_id(
                    value,
                    prefix="conversation",
                )

    def mark_replayed(self) -> None:
        with self._lock:
            if not self._finished:
                self.replayed = True

    def record(
        self,
        stage: str,
        *,
        status: str,
        elapsed_ms: float,
        provider: Any = None,
        attempt: int | None = None,
        outcome: Any = None,
        result_ids: dict[str, Any] | None = None,
        failure_kind: str | None = None,
        error: BaseException | str | None = None,
    ) -> dict[str, Any]:
        safe_stage = stage if stage in _STAGES else "application_turn"
        safe_status = status if status in _STATUSES else "failure"
        event: dict[str, Any] = {
            "event": "mary.turn.stage",
            "schema": 1,
            "request_id": self.request_id,
            "core_instance_id": self.core_instance_id,
            "stage": safe_stage,
            "status": safe_status,
            "elapsed_ms": round(max(0.0, min(float(elapsed_ms), 86_400_000.0)), 2),
        }
        if self.upstream_request_hash:
            event["upstream_request_hash"] = self.upstream_request_hash
        if self.turn_id:
            event["turn_id"] = self.turn_id
        if self.conversation_id:
            event["conversation_id"] = self.conversation_id
        if provider not in (None, ""):
            event["provider"] = bounded_identifier(
                provider,
                default_prefix="provider",
            )[:64]
        if attempt is not None:
            event["attempt"] = max(1, min(99, int(attempt)))
        if outcome not in (None, ""):
            safe_outcome = safe_link_identifier(outcome)
            if safe_outcome:
                event["outcome"] = safe_outcome[:64]
        if isinstance(result_ids, dict):
            safe_results: dict[str, Any] = {}
            for key in sorted(_RESULT_ID_KEYS):
                raw = result_ids.get(key)
                if isinstance(raw, (list, tuple)):
                    values = [
                        safe for item in raw[:8]
                        if (safe := safe_link_identifier(item))
                    ]
                    if values:
                        safe_results[key] = values
                else:
                    safe = safe_link_identifier(raw)
                    if safe:
                        safe_results[key] = safe
            if safe_results:
                event["result_ids"] = safe_results
        if safe_status == "failure":
            kind = failure_kind or classify_failure(
                error if isinstance(error, BaseException) else None
            )
            event["failure_kind"] = (
                kind if kind in _FAILURE_KINDS else "unknown"
            )
            if error is not None:
                event["error_type"] = bounded_type_name(error)

        with self._lock:
            if self._finished:
                return {}
            if len(self._stages) >= self.max_stages:
                self._dropped_stages += 1
                return {}
            event["sequence"] = len(self._stages) + 1
            self._stages.append(dict(event))
        _LOGGER.info(json.dumps(event, separators=(",", ":"), sort_keys=True))
        return event

    @contextmanager
    def stage(
        self,
        name: str,
        *,
        provider: Any = None,
        attempt: int | None = None,
        failure_kind: str = "application_exception",
    ) -> Iterator[None]:
        started = monotonic()
        try:
            yield
        except BaseException as exc:
            self.record(
                name,
                status="failure",
                elapsed_ms=(monotonic() - started) * 1000.0,
                provider=provider,
                attempt=attempt,
                failure_kind=classify_failure(exc, default=failure_kind),
                error=exc,
            )
            raise
        else:
            self.record(
                name,
                status="success",
                elapsed_ms=(monotonic() - started) * 1000.0,
                provider=provider,
                attempt=attempt,
            )

    def finish(
        self,
        *,
        outcome: str,
        failure_kind: str | None = None,
        error: BaseException | str | None = None,
    ) -> dict[str, Any]:
        with self._lock:
            if self._finished:
                return self.snapshot()
            self._finished = True
            failed_stage = next(
                (
                    item["stage"]
                    for item in reversed(self._stages)
                    if item.get("status") == "failure"
                ),
                None,
            )
            event: dict[str, Any] = {
                "event": "mary.turn.complete",
                "schema": 1,
                "request_id": self.request_id,
                "core_instance_id": self.core_instance_id,
                "outcome": outcome if outcome in _TERMINAL_OUTCOMES else "failure",
                "status": "success" if outcome in {"success", "replayed"} else "failure",
                "total_elapsed_ms": round(
                    max(
                        0.0,
                        min(
                            (monotonic() - self.started) * 1000.0,
                            86_400_000.0,
                        ),
                    ),
                    2,
                ),
                "stage_count": len(self._stages),
                "dropped_stage_count": self._dropped_stages,
            }
            if self.upstream_request_hash:
                event["upstream_request_hash"] = self.upstream_request_hash
            if self.turn_id:
                event["turn_id"] = self.turn_id
            if self.conversation_id:
                event["conversation_id"] = self.conversation_id
            if failed_stage:
                event["failed_stage"] = failed_stage
            if outcome not in {"success", "replayed"}:
                kind = failure_kind or classify_failure(
                    error if isinstance(error, BaseException) else None
                )
                event["failure_kind"] = (
                    kind if kind in _FAILURE_KINDS else "unknown"
                )
                if error is not None:
                    event["error_type"] = bounded_type_name(error)
            if self.core_uptime_ms is not None:
                try:
                    event["core_uptime_ms"] = round(
                        max(0.0, float(self.core_uptime_ms())),
                        2,
                    )
                except Exception:
                    pass
            snapshot = {
                **event,
                "stages": [dict(item) for item in self._stages],
            }
            self._completion = snapshot
        _LOGGER.info(json.dumps(event, separators=(",", ":"), sort_keys=True))
        if self.sink is not None:
            try:
                self.sink(snapshot)
            except Exception:
                pass
        return snapshot

    def latest_failure_kind(self, default: str = "unknown") -> str:
        with self._lock:
            for item in reversed(self._stages):
                if item.get("status") == "failure":
                    kind = str(item.get("failure_kind") or "")
                    return kind if kind in _FAILURE_KINDS else default
        return default

    def snapshot(self) -> dict[str, Any]:
        with self._lock:
            if self._completion is not None:
                return {
                    **self._completion,
                    "stages": [dict(item) for item in self._completion["stages"]],
                }
            return {
                "request_id": self.request_id,
                "core_instance_id": self.core_instance_id,
                "turn_id": self.turn_id,
                "conversation_id": self.conversation_id,
                "finished": self._finished,
                "replayed": self.replayed,
                "upstream_request_hash": self.upstream_request_hash,
                "dropped_stage_count": self._dropped_stages,
                "stages": [dict(item) for item in self._stages],
            }


def current_turn_trace() -> TurnTraceRecorder | None:
    return _CURRENT.get()


def bind_turn_trace(recorder: TurnTraceRecorder) -> Token:
    return _CURRENT.set(recorder)


def reset_turn_trace(token: Token) -> None:
    _CURRENT.reset(token)


@contextmanager
def observe_turn_stage(
    name: str,
    *,
    provider: Any = None,
    attempt: int | None = None,
    failure_kind: str = "application_exception",
) -> Iterator[None]:
    recorder = current_turn_trace()
    if recorder is None:
        yield
        return
    with recorder.stage(
        name,
        provider=provider,
        attempt=attempt,
        failure_kind=failure_kind,
    ):
        yield


def record_turn_stage(name: str, **values: Any) -> None:
    recorder = current_turn_trace()
    if recorder is not None:
        recorder.record(name, **values)


def emit_core_started(instance_id: Any) -> None:
    event = {
        "event": "mary.core.started",
        "schema": 1,
        "core_instance_id": bounded_identifier(
            instance_id,
            default_prefix="core",
        ),
    }
    _LOGGER.info(json.dumps(event, separators=(",", ":"), sort_keys=True))