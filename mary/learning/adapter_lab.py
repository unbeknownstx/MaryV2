"""Model/LoRA experiment registry for MaryV2.

This module does not load models or grant a model character authority.  It
tracks compatible adapter configurations and comparable evaluation results so
premade roleplay/conversation LoRAs and future Mary-trained adapters can be
measured rather than adopted by intuition alone.
"""
from __future__ import annotations

from dataclasses import asdict, dataclass, field
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Iterable
import json


@dataclass(frozen=True)
class AdapterSpec:
    adapter_id: str
    base_model: str
    path_or_repo: str
    scale: float = 1.0
    format: str = "unknown"
    license: str = "unknown"
    purpose: str = "character_style"
    enabled: bool = True

    def to_dict(self) -> dict[str, Any]:
        payload = asdict(self)
        payload["scale"] = round(max(0.0, min(2.0, float(self.scale))), 3)
        return payload


@dataclass(frozen=True)
class AdapterConfiguration:
    config_id: str
    base_model: str
    adapters: tuple[AdapterSpec, ...] = ()
    runtime: str = "llama.cpp"
    notes: str = ""

    def validate(self) -> tuple[bool, list[str]]:
        errors: list[str] = []
        normalized_base = self.base_model.strip().casefold()
        if not normalized_base:
            errors.append("base model is required")
        for adapter in self.adapters:
            if adapter.base_model.strip().casefold() != normalized_base:
                errors.append(
                    f"adapter {adapter.adapter_id} targets {adapter.base_model}, not {self.base_model}"
                )
        return not errors, errors

    def to_dict(self) -> dict[str, Any]:
        valid, errors = self.validate()
        return {
            "config_id": self.config_id,
            "base_model": self.base_model,
            "runtime": self.runtime,
            "notes": self.notes[:500],
            "adapters": [item.to_dict() for item in self.adapters],
            "valid": valid,
            "errors": errors,
        }


@dataclass(frozen=True)
class AdapterEvaluation:
    config_id: str
    scores: dict[str, float]
    latency_ms: float | None = None
    evaluator: str = "mary_eval_suite"
    created_at: str = field(default_factory=lambda: datetime.now(timezone.utc).isoformat())

    @property
    def mary_fit(self) -> float:
        weights = {
            "mary_likeness": .28,
            "naturalism": .18,
            "reasoning": .14,
            "context_adherence": .14,
            "emotional_fit": .12,
            "wit": .08,
            "brevity": .06,
        }
        total = 0.0
        used = 0.0
        for key, weight in weights.items():
            if key in self.scores:
                total += max(0.0, min(1.0, float(self.scores[key]))) * weight
                used += weight
        return total / used if used else 0.0

    def to_dict(self) -> dict[str, Any]:
        return {
            "config_id": self.config_id,
            "scores": {k: round(max(0.0, min(1.0, float(v))), 3) for k, v in self.scores.items()},
            "mary_fit": round(self.mary_fit, 3),
            "latency_ms": None if self.latency_ms is None else round(max(0.0, float(self.latency_ms)), 2),
            "evaluator": self.evaluator,
            "created_at": self.created_at,
        }


class AdapterLab:
    def __init__(self, path: str | Path | None = None) -> None:
        self.path = Path(path) if path is not None else None
        self.configurations: dict[str, AdapterConfiguration] = {}
        self.evaluations: list[AdapterEvaluation] = []
        if self.path and self.path.exists():
            self._load()

    def register(self, config: AdapterConfiguration) -> AdapterConfiguration:
        valid, errors = config.validate()
        if not valid:
            raise ValueError("; ".join(errors))
        self.configurations[config.config_id] = config
        self.save()
        return config

    def record(self, evaluation: AdapterEvaluation) -> AdapterEvaluation:
        if evaluation.config_id not in self.configurations:
            raise KeyError(f"unknown adapter configuration: {evaluation.config_id}")
        self.evaluations.append(evaluation)
        self.evaluations[:] = self.evaluations[-500:]
        self.save()
        return evaluation

    def leaderboard(self, limit: int = 20) -> list[dict[str, Any]]:
        latest: dict[str, AdapterEvaluation] = {}
        for item in self.evaluations:
            latest[item.config_id] = item
        ranked = sorted(latest.values(), key=lambda item: (item.mary_fit, -(item.latency_ms or 0.0)), reverse=True)
        return [item.to_dict() for item in ranked[: max(1, int(limit))]]

    def snapshot(self) -> dict[str, Any]:
        return {
            "configurations": [item.to_dict() for item in self.configurations.values()],
            "leaderboard": self.leaderboard(),
            "policy": "adapters influence generation only; canonical Mary identity/character remains runtime-owned",
        }

    def save(self) -> None:
        if self.path is None:
            return
        self.path.parent.mkdir(parents=True, exist_ok=True)
        payload = {
            "version": 1,
            "configurations": [item.to_dict() for item in self.configurations.values()],
            "evaluations": [item.to_dict() for item in self.evaluations[-500:]],
        }
        temporary = self.path.with_name(f".{self.path.name}.tmp")
        temporary.write_text(json.dumps(payload, indent=2, ensure_ascii=False), encoding="utf-8")
        temporary.replace(self.path)

    def _load(self) -> None:
        try:
            payload = json.loads(self.path.read_text(encoding="utf-8")) if self.path else {}
        except Exception:
            return
        for item in payload.get("configurations", []):
            try:
                adapters = tuple(AdapterSpec(**adapter) for adapter in item.get("adapters", []))
                config = AdapterConfiguration(
                    config_id=item["config_id"],
                    base_model=item["base_model"],
                    adapters=adapters,
                    runtime=item.get("runtime", "llama.cpp"),
                    notes=item.get("notes", ""),
                )
                if config.validate()[0]:
                    self.configurations[config.config_id] = config
            except Exception:
                continue
        for item in payload.get("evaluations", []):
            try:
                self.evaluations.append(
                    AdapterEvaluation(
                        config_id=item["config_id"],
                        scores=dict(item.get("scores") or {}),
                        latency_ms=item.get("latency_ms"),
                        evaluator=item.get("evaluator", "mary_eval_suite"),
                        created_at=item.get("created_at") or datetime.now(timezone.utc).isoformat(),
                    )
                )
            except Exception:
                continue
