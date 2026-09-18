"""Reviewed optional model/adapter candidate catalog.

The catalog is source metadata only. It never downloads weights, loads a model,
or grants a candidate any authority over Mary.  Its purpose is to make internet
experimentation reproducible: exact artifact, exact compatible base, license,
and hash where available.
"""
from __future__ import annotations

from dataclasses import dataclass, field
import json
from pathlib import Path
from typing import Any


@dataclass(frozen=True)
class ModelCandidate:
    candidate_id: str
    kind: str
    runtime: str
    repository: str
    filename: str
    sha256: str = ""
    license: str = "unknown"
    required_base: str | None = None
    upstream_base: str | None = None
    roles: tuple[str, ...] = ()
    notes: str = ""
    metadata: dict[str, Any] = field(default_factory=dict)

    def to_dict(self) -> dict[str, Any]:
        return {
            "id": self.candidate_id,
            "kind": self.kind,
            "runtime": self.runtime,
            "repository": self.repository,
            "filename": self.filename,
            "sha256": self.sha256,
            "license": self.license,
            "required_base": self.required_base,
            "upstream_base": self.upstream_base,
            "roles": list(self.roles),
            "notes": self.notes[:500],
            "metadata": dict(self.metadata),
        }


class ModelCandidateCatalog:
    VERSION = "1"

    def __init__(self, path: str | Path | None = None) -> None:
        self.path = Path(path) if path is not None else None
        self.candidates: dict[str, ModelCandidate] = {}
        self.error: str | None = None
        if self.path is not None:
            self.load()

    def load(self) -> int:
        self.candidates.clear()
        self.error = None
        if self.path is None or not self.path.exists():
            return 0
        try:
            payload = json.loads(self.path.read_text(encoding="utf-8"))
        except Exception as exc:  # noqa: BLE001 - status should degrade, not fail Mary boot
            self.error = f"{type(exc).__name__}: invalid candidate catalog"
            return 0
        for raw in list(payload.get("candidates") or [])[:100]:
            if not isinstance(raw, dict):
                continue
            candidate_id = str(raw.get("id") or "").strip()
            repository = str(raw.get("repository") or "").strip()
            filename = str(raw.get("filename") or "").strip()
            if not candidate_id or not repository or not filename:
                continue
            known = {
                "id", "kind", "runtime", "repository", "filename", "sha256",
                "license", "required_base", "upstream_base", "role", "notes",
            }
            metadata = {str(k): v for k, v in raw.items() if k not in known}
            self.candidates[candidate_id] = ModelCandidate(
                candidate_id=candidate_id,
                kind=str(raw.get("kind") or "unknown")[:80],
                runtime=str(raw.get("runtime") or "unknown")[:80],
                repository=repository[:300],
                filename=filename[:300],
                sha256=str(raw.get("sha256") or "").strip().lower()[:128],
                license=str(raw.get("license") or "unknown")[:120],
                required_base=(str(raw.get("required_base"))[:300] if raw.get("required_base") else None),
                upstream_base=(str(raw.get("upstream_base"))[:300] if raw.get("upstream_base") else None),
                roles=tuple(str(item)[:100] for item in list(raw.get("role") or [])[:20]),
                notes=str(raw.get("notes") or "")[:1000],
                metadata=metadata,
            )
        return len(self.candidates)

    def get(self, candidate_id: str) -> ModelCandidate | None:
        return self.candidates.get(str(candidate_id or "").strip())

    def compatibility(
        self,
        *,
        base_candidate_id: str,
        adapter_candidate_id: str,
    ) -> dict[str, Any]:
        base = self.get(base_candidate_id)
        adapter = self.get(adapter_candidate_id)
        if base is None:
            raise KeyError(base_candidate_id)
        if adapter is None:
            raise KeyError(adapter_candidate_id)

        base_lineage = str(
            base.upstream_base
            or base.required_base
            or base.metadata.get("upstream_base")
            or ""
        ).strip()
        adapter_lineage = str(
            adapter.required_base
            or adapter.upstream_base
            or adapter.metadata.get("upstream_base")
            or ""
        ).strip()
        exact_base = bool(
            base_lineage
            and adapter_lineage
            and base_lineage == adapter_lineage
        )
        runtime_compatible = (
            str(base.runtime).casefold() == str(adapter.runtime).casefold()
        )
        is_adapter = adapter.kind == "lora_adapter"
        direct = bool(is_adapter and exact_base and runtime_compatible)
        reasons: list[str] = []
        if not is_adapter:
            reasons.append("candidate is not a LoRA adapter")
        if not base_lineage:
            reasons.append("base candidate does not declare upstream lineage")
        if not adapter_lineage:
            reasons.append("adapter does not declare required base lineage")
        elif base_lineage and not exact_base:
            reasons.append(
                f"exact base mismatch: adapter={adapter_lineage} base={base_lineage}"
            )
        if not runtime_compatible:
            reasons.append(
                f"runtime mismatch: adapter={adapter.runtime} base={base.runtime}"
            )
        return {
            "base_candidate_id": base.candidate_id,
            "adapter_candidate_id": adapter.candidate_id,
            "base_lineage": base_lineage,
            "adapter_lineage": adapter_lineage,
            "exact_base": exact_base,
            "runtime_compatible": runtime_compatible,
            "directly_testable": direct,
            "reasons": reasons,
            "policy": (
                "exact upstream base and runtime required for direct adapter tests; "
                "candidate metadata never grants Mary authority"
            ),
        }

    def experiment_matrix(
        self,
        *,
        base_candidate_id: str,
        adapter_candidate_ids: list[str] | tuple[str, ...],
    ) -> dict[str, Any]:
        base = self.get(base_candidate_id)
        if base is None:
            raise KeyError(base_candidate_id)
        checks = [
            self.compatibility(
                base_candidate_id=base_candidate_id,
                adapter_candidate_id=adapter_id,
            )
            for adapter_id in adapter_candidate_ids
        ]
        directly_testable = [
            item["adapter_candidate_id"]
            for item in checks
            if item["directly_testable"]
        ]
        return {
            "base_candidate_id": base_candidate_id,
            "control": {
                "id": "base_only",
                "base_candidate_id": base_candidate_id,
                "adapters": [],
            },
            "adapter_arms": [
                {
                    "id": f"adapter:{adapter_id}",
                    "base_candidate_id": base_candidate_id,
                    "adapters": [adapter_id],
                }
                for adapter_id in directly_testable
            ],
            "compatibility": checks,
            "stacking": (
                "single-adapter arms by default; multi-adapter stacking requires "
                "a separate explicit exact-base/runtime check"
            ),
            "promotion": "creator-reviewed experiment only; never automatic",
        }

    def snapshot(self) -> dict[str, Any]:
        return {
            "version": self.VERSION,
            "path_present": bool(self.path and self.path.exists()),
            "count": len(self.candidates),
            "candidates": [item.to_dict() for item in self.candidates.values()],
            "error": self.error,
            "policy": "reviewed optional assets only; no automatic download/load/authority",
        }
