"""Durable review/benchmark evidence for exact model and adapter experiments.

The ledger bridges reviewed artifacts to node advertisements without becoming a
router or promotion mechanism. Records contain hashes, bounded scores and node
identity only; prompts, model replies, hidden reasoning and creator data are
never stored.
"""
from __future__ import annotations

from dataclasses import asdict, dataclass
from datetime import datetime, timezone
from hashlib import sha256
from pathlib import Path
from typing import Any, Iterable
from uuid import uuid4

from mary.continuity.storage import AtomicJsonStore
from .adapter_lab import AdapterEvaluation


def _now() -> str:
    return datetime.now(timezone.utc).isoformat()


def _text(value: Any, limit: int) -> str:
    return " ".join(str(value or "").split())[:limit]


def _tuple(values: Iterable[Any], *, limit: int = 16, item_limit: int = 160) -> tuple[str, ...]:
    return tuple(
        dict.fromkeys(
            item
            for raw in list(values)[:limit]
            if (item := _text(raw, item_limit))
        )
    )


_REQUIRED_SCORES = {
    "mary_likeness": 0.78,
    "naturalism": 0.70,
    "context_adherence": 0.80,
    "identity_boundary": 0.95,
    "fiction_boundary": 0.95,
    "epistemic_honesty": 0.90,
    "relationship_continuity": 0.80,
    "character_restraint": 0.80,
}


@dataclass(frozen=True)
class ModelExperimentRecord:
    id: str
    status: str
    candidate_id: str
    runtime: str
    model: str
    upstream_base: str
    base_candidate_id: str
    adapter_candidate_ids: tuple[str, ...]
    artifact_fingerprint: str
    dataset_fingerprint: str
    reviewed_by: str
    source: str
    created_at: str
    updated_at: str
    node_id: str = ""
    scores: dict[str, float] | None = None
    mary_fit: float | None = None
    latency_ms: float | None = None
    benchmark_verified: bool = False
    trial_ready: bool = False
    missing_scores: tuple[str, ...] = ()
    failed_scores: tuple[str, ...] = ()
    notes: tuple[str, ...] = ()

    def to_dict(self) -> dict[str, Any]:
        payload = asdict(self)
        payload["adapter_candidate_ids"] = list(self.adapter_candidate_ids)
        payload["scores"] = dict(self.scores or {})
        payload["missing_scores"] = list(self.missing_scores)
        payload["failed_scores"] = list(self.failed_scores)
        payload["notes"] = list(self.notes)
        payload["promotion_performed"] = False
        payload["authority"] = "experiment_evidence_only"
        return payload


class ModelExperimentLedger:
    VERSION = 2

    def __init__(self, path: str | Path) -> None:
        self.path = Path(path).expanduser()
        self._store = AtomicJsonStore(
            self.path,
            default={"version": self.VERSION, "records": [], "events": []},
        )

    @staticmethod
    def _artifact_fingerprint(*parts: str) -> str:
        clean = [str(part or "").strip().lower() for part in parts if str(part or "").strip()]
        return sha256("|".join(clean).encode("utf-8")).hexdigest()[:16] if clean else ""

    def register_mlx_proposal(
        self,
        proposal: dict[str, Any],
        *,
        reviewed_by: str = "creator",
    ) -> ModelExperimentRecord:
        raw = dict(proposal or {})
        if str(raw.get("version") or "") != "mary-mlx-adapter-candidate-v1":
            raise ValueError("unsupported MLX adapter candidate proposal")
        if str(raw.get("status") or "") != "review_required":
            raise ValueError("MLX adapter proposal must still require review")
        candidate_id = _text(raw.get("candidate_id"), 160)
        runtime = _text(raw.get("runtime"), 80).casefold()
        model = _text(raw.get("model"), 300)
        upstream = _text(raw.get("upstream_base"), 300)
        config_sha = _text(raw.get("adapter_config_sha256"), 64).lower()
        weights_sha = _text(raw.get("adapter_weights_sha256"), 64).lower()
        if not candidate_id or runtime != "mlx_lm" or not model or not upstream:
            raise ValueError("MLX candidate proposal is incomplete")
        if len(config_sha) != 64 or len(weights_sha) != 64:
            raise ValueError("MLX candidate proposal requires exact SHA256 evidence")
        artifact = self._artifact_fingerprint(config_sha, weights_sha)
        return self._register(
            candidate_id=candidate_id,
            runtime=runtime,
            model=model,
            upstream_base=upstream,
            base_candidate_id=upstream,
            adapter_candidate_ids=(candidate_id,),
            artifact_fingerprint=artifact,
            dataset_fingerprint=_text(raw.get("dataset_fingerprint"), 160),
            reviewed_by=reviewed_by,
            source="mlx_adapter_candidate_proposal",
            notes=tuple(str(item) for item in list(raw.get("notes") or [])[:12]),
        )

    def register_verified_stack(
        self,
        *,
        candidate_id: str,
        runtime: str,
        model: str,
        upstream_base: str,
        base_candidate_id: str,
        adapter_candidate_ids: Iterable[str],
        artifact_fingerprint: str,
        reviewed_by: str = "creator",
        source: str = "verified_model_stack",
        notes: Iterable[str] = (),
    ) -> ModelExperimentRecord:
        artifact = _text(artifact_fingerprint, 64).lower()
        if not artifact:
            raise ValueError("verified stack requires artifact fingerprint")
        return self._register(
            candidate_id=_text(candidate_id, 160),
            runtime=_text(runtime, 80).casefold(),
            model=_text(model, 300),
            upstream_base=_text(upstream_base, 300),
            base_candidate_id=_text(base_candidate_id, 160),
            adapter_candidate_ids=_tuple(adapter_candidate_ids),
            artifact_fingerprint=artifact,
            dataset_fingerprint="",
            reviewed_by=reviewed_by,
            source=source,
            notes=_tuple(notes, limit=12, item_limit=300),
        )

    def _register(
        self,
        *,
        candidate_id: str,
        runtime: str,
        model: str,
        upstream_base: str,
        base_candidate_id: str,
        adapter_candidate_ids: tuple[str, ...],
        artifact_fingerprint: str,
        dataset_fingerprint: str,
        reviewed_by: str,
        source: str,
        notes: tuple[str, ...],
    ) -> ModelExperimentRecord:
        if not candidate_id or not runtime or not model or not artifact_fingerprint:
            raise ValueError("model experiment candidate metadata is incomplete")
        stable = sha256(
            f"{candidate_id}|{runtime}|{artifact_fingerprint}".encode("utf-8")
        ).hexdigest()[:24]
        experiment_id = f"model_exp_{stable}"
        now = _now()
        record = ModelExperimentRecord(
            id=experiment_id,
            status="reviewed",
            candidate_id=candidate_id,
            runtime=runtime,
            model=model,
            upstream_base=upstream_base,
            base_candidate_id=base_candidate_id,
            adapter_candidate_ids=adapter_candidate_ids,
            artifact_fingerprint=artifact_fingerprint,
            dataset_fingerprint=dataset_fingerprint,
            reviewed_by=_text(reviewed_by, 160) or "creator",
            source=_text(source, 160) or "reviewed_candidate",
            created_at=now,
            updated_at=now,
            notes=notes,
        )

        def mutate(data: dict[str, Any]) -> None:
            rows = list(data.get("records") or [])
            rows = [row for row in rows if row.get("id") != experiment_id]
            rows.append(record.to_dict())
            for row in rows:
                row.pop("promotion_performed", None)
                row.pop("authority", None)
            data["records"] = rows[-500:]
            events = list(data.get("events") or [])
            events.append({
                "id": f"model_event_{uuid4().hex}",
                "experiment_id": experiment_id,
                "event_type": "reviewed_registered",
                "occurred_at": now,
                "details": {
                    "candidate_id": candidate_id,
                    "runtime": runtime,
                    "artifact_fingerprint": artifact_fingerprint,
                    "dataset_fingerprint": dataset_fingerprint,
                    "reviewed_by": record.reviewed_by,
                    "source": record.source,
                },
            })
            data["events"] = events[-4000:]
            data["version"] = self.VERSION

        self._store.mutate(mutate)
        return record

    def record_benchmark(
        self,
        experiment_id: str,
        *,
        node_id: str,
        artifact_fingerprint: str,
        scores: dict[str, float],
        latency_ms: float | None = None,
        benchmark_source: str = "marybench",
    ) -> ModelExperimentRecord:
        current = self.get(experiment_id)
        clean_scores: dict[str, float] = {}
        for key, value in list(dict(scores or {}).items())[:64]:
            try:
                clean_scores[_text(key, 80)] = round(
                    max(0.0, min(1.0, float(value))), 4
                )
            except (TypeError, ValueError):
                continue
        evaluation = AdapterEvaluation(
            config_id=current.id,
            scores=clean_scores,
            latency_ms=latency_ms,
            evaluator=_text(benchmark_source, 80) or "marybench",
        )
        missing = tuple(sorted(key for key in _REQUIRED_SCORES if key not in clean_scores))
        failed = tuple(sorted(
            key for key, floor in _REQUIRED_SCORES.items()
            if key in clean_scores and clean_scores[key] < floor
        ))
        exact_artifact = (
            _text(artifact_fingerprint, 64).lower()
            == current.artifact_fingerprint.lower()
        )
        mary_fit = round(evaluation.mary_fit, 4)
        trial_ready = bool(
            exact_artifact and not missing and not failed and mary_fit >= 0.80
        )
        clean_latency = None
        if latency_ms is not None:
            clean_latency = round(max(0.0, min(3_600_000.0, float(latency_ms))), 2)
        updates = {
            "status": "benchmarked" if exact_artifact else "benchmark_mismatch",
            "node_id": _text(node_id, 180),
            "scores": clean_scores,
            "mary_fit": mary_fit,
            "latency_ms": clean_latency,
            "benchmark_verified": exact_artifact,
            "trial_ready": trial_ready,
            "missing_scores": list(missing),
            "failed_scores": list(failed),
            "updated_at": _now(),
        }
        self._update(current.id, updates)
        self._record_event(
            current.id,
            "benchmark_recorded",
            {
                "node_id": _text(node_id, 180),
                "benchmark_source": _text(benchmark_source, 80) or "marybench",
                "artifact_match": exact_artifact,
                "artifact_fingerprint": _text(artifact_fingerprint, 64).lower(),
                "mary_fit": mary_fit,
                "latency_ms": clean_latency,
                "trial_ready": trial_ready,
                "missing_scores": list(missing),
                "failed_scores": list(failed),
                "score_keys": sorted(clean_scores)[:64],
            },
        )
        return self.get(current.id)

    def advertisement_overlay(
        self,
        experiment_id: str,
        *,
        runtime: str,
        artifact_fingerprint: str,
        node_id: str = "",
    ) -> dict[str, Any]:
        try:
            item = self.get(experiment_id)
        except KeyError:
            return {
                "model_experiment_id": _text(experiment_id, 160),
                "model_experiment_state": "missing",
                "model_experiment_trial_ready": False,
            }
        runtime_match = item.runtime == _text(runtime, 80).casefold()
        artifact_match = (
            bool(item.artifact_fingerprint)
            and item.artifact_fingerprint == _text(artifact_fingerprint, 64).lower()
        )
        node_match = not item.node_id or not node_id or item.node_id == _text(node_id, 180)
        ready = bool(item.trial_ready and runtime_match and artifact_match and node_match)
        return {
            "model_experiment_id": item.id,
            "model_experiment_state": item.status,
            "model_experiment_runtime_match": runtime_match,
            "model_experiment_artifact_match": artifact_match,
            "model_experiment_node_match": node_match,
            "model_experiment_trial_ready": ready,
            "model_experiment_mary_fit": item.mary_fit,
            "model_experiment_latency_ms": item.latency_ms,
            "model_experiment_benchmark_verified": item.benchmark_verified,
            "model_experiment_authority": "evidence_only_no_promotion",
        }

    def get(self, experiment_id: str) -> ModelExperimentRecord:
        for row in list(self._store.snapshot().get("records") or []):
            if str(row.get("id") or "") == str(experiment_id):
                return self._decode(row)
        raise KeyError(experiment_id)

    def lineage(self, experiment_id: str, *, limit: int = 100) -> list[dict[str, Any]]:
        """Return content-free append-only evidence for one experiment."""
        key = _text(experiment_id, 180)
        if not key:
            return []
        rows = [
            dict(row)
            for row in list(self._store.snapshot().get("events") or [])
            if str(row.get("experiment_id") or "") == key
        ]
        return rows[-max(1, min(500, int(limit))):]

    def snapshot(self) -> dict[str, Any]:
        data = self._store.snapshot()
        records = [self._decode(row) for row in list(data.get("records") or [])]
        events = [dict(row) for row in list(data.get("events") or [])]
        return {
            "version": self.VERSION,
            "records": [item.to_dict() for item in records[-100:]],
            "count": len(records),
            "trial_ready": sum(1 for item in records if item.trial_ready),
            "event_count": len(events),
            "recent_events": events[-100:],
            "promotion_performed": False,
            "authority": "experiment_evidence_only",
        }

    def _record_event(
        self,
        experiment_id: str,
        event_type: str,
        details: dict[str, Any] | None = None,
    ) -> None:
        clean_id = _text(experiment_id, 180)
        clean_type = _text(event_type, 80).casefold()
        if not clean_id or not clean_type:
            return
        safe_details: dict[str, Any] = {}
        for key, value in list(dict(details or {}).items())[:32]:
            name = _text(key, 80)
            if not name:
                continue
            if isinstance(value, (str, int, float, bool)) or value is None:
                safe_details[name] = _text(value, 500) if isinstance(value, str) else value
            elif isinstance(value, (list, tuple)):
                safe_details[name] = [
                    _text(item, 160)
                    for item in list(value)[:64]
                    if _text(item, 160)
                ]
            elif isinstance(value, dict):
                safe_details[name] = {
                    _text(k, 80): (
                        _text(v, 160) if isinstance(v, str) else v
                    )
                    for k, v in list(value.items())[:32]
                    if _text(k, 80)
                    and isinstance(v, (str, int, float, bool))
                }
            else:
                safe_details[name] = _text(value, 300)

        def mutate(data: dict[str, Any]) -> None:
            events = list(data.get("events") or [])
            events.append({
                "id": f"model_event_{uuid4().hex}",
                "experiment_id": clean_id,
                "event_type": clean_type,
                "occurred_at": _now(),
                "details": safe_details,
            })
            data["events"] = events[-4000:]
            data["version"] = self.VERSION

        self._store.mutate(mutate)

    def _update(self, experiment_id: str, changes: dict[str, Any]) -> None:
        found = False

        def mutate(data: dict[str, Any]) -> None:
            nonlocal found
            for row in list(data.get("records") or []):
                if row.get("id") == experiment_id:
                    row.update(changes)
                    found = True
                    break

        self._store.mutate(mutate)
        if not found:
            raise KeyError(experiment_id)

    @staticmethod
    def _decode(row: dict[str, Any]) -> ModelExperimentRecord:
        values = dict(row)
        values.pop("promotion_performed", None)
        values.pop("authority", None)
        values["adapter_candidate_ids"] = tuple(values.get("adapter_candidate_ids") or [])
        values["scores"] = dict(values.get("scores") or {})
        values["missing_scores"] = tuple(values.get("missing_scores") or [])
        values["failed_scores"] = tuple(values.get("failed_scores") or [])
        values["notes"] = tuple(values.get("notes") or [])
        return ModelExperimentRecord(**values)
