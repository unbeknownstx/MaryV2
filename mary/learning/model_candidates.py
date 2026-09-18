"""Reviewed optional model/adapter candidate catalog.

The catalog is source metadata only. It never downloads weights, loads a model,
or grants a candidate any authority over Mary.  Its purpose is to make internet
experimentation reproducible: exact artifact, exact compatible base, license,
and hash where available.
"""
from __future__ import annotations

from dataclasses import dataclass, field
from datetime import datetime, timezone
import hashlib
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
    VERSION = "2"
    VERIFICATION_VERSION = 1

    def __init__(
        self,
        path: str | Path | None = None,
        *,
        asset_root: str | Path | None = None,
        verification_path: str | Path | None = None,
    ) -> None:
        self.path = Path(path) if path is not None else None
        self.asset_root = Path(asset_root).expanduser() if asset_root is not None else None
        self.verification_path = (
            Path(verification_path).expanduser()
            if verification_path is not None
            else None
        )
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

    @staticmethod
    def _now() -> str:
        return datetime.now(timezone.utc).isoformat()

    @staticmethod
    def _asset_group(candidate: ModelCandidate) -> str:
        group = str(candidate.metadata.get("asset_group") or "").strip().lower()
        if not group:
            group = (
                "llm"
                if candidate.kind in {"base_model", "fine_tuned_model", "lora_adapter"}
                else "misc"
            )
        return group if group in {"llm", "stt", "vad", "vision", "motion", "tts", "misc"} else "misc"

    def artifact_path(
        self,
        candidate_id: str,
        *,
        asset_root: str | Path | None = None,
    ) -> Path:
        candidate = self.get(candidate_id)
        if candidate is None:
            raise KeyError(candidate_id)
        root = Path(asset_root).expanduser() if asset_root is not None else self.asset_root
        if root is None:
            raise ValueError("asset_root is required to inspect model artifacts")
        return root / self._asset_group(candidate) / candidate.filename

    @staticmethod
    def _sha256_file(path: Path) -> str:
        digest = hashlib.sha256()
        with path.open("rb") as handle:
            for chunk in iter(lambda: handle.read(1024 * 1024), b""):
                digest.update(chunk)
        return digest.hexdigest()

    def _load_verifications(self) -> dict[str, Any]:
        empty = {"version": self.VERIFICATION_VERSION, "artifacts": {}}
        if self.verification_path is None or not self.verification_path.exists():
            return empty
        try:
            raw = json.loads(self.verification_path.read_text(encoding="utf-8"))
        except Exception:
            return empty
        if not isinstance(raw, dict):
            return empty
        artifacts = raw.get("artifacts")
        return {
            "version": self.VERIFICATION_VERSION,
            "artifacts": dict(artifacts) if isinstance(artifacts, dict) else {},
        }

    def _save_verifications(self, payload: dict[str, Any]) -> None:
        if self.verification_path is None:
            return
        self.verification_path.parent.mkdir(parents=True, exist_ok=True)
        temporary = self.verification_path.with_name(
            f".{self.verification_path.name}.tmp"
        )
        temporary.write_text(
            json.dumps(
                {
                    "version": self.VERIFICATION_VERSION,
                    "artifacts": dict(payload.get("artifacts") or {}),
                },
                indent=2,
                ensure_ascii=False,
                sort_keys=True,
            ),
            encoding="utf-8",
        )
        temporary.replace(self.verification_path)

    def artifact_status(
        self,
        candidate_id: str,
        *,
        asset_root: str | Path | None = None,
    ) -> dict[str, Any]:
        candidate = self.get(candidate_id)
        if candidate is None:
            raise KeyError(candidate_id)
        path = self.artifact_path(candidate_id, asset_root=asset_root)
        base = {
            "candidate_id": candidate.candidate_id,
            "kind": candidate.kind,
            "runtime": candidate.runtime,
            "filename": candidate.filename,
            "asset_group": self._asset_group(candidate),
            "expected_sha256_present": bool(candidate.sha256),
            "required_base": candidate.required_base,
            "authority": "local artifact evidence only",
            "auto_promoted": False,
        }
        if not path.exists() or not path.is_file():
            return {
                **base,
                "state": "absent",
                "present": False,
                "verified": False,
                "ready_for_benchmark": False,
            }

        stat = path.stat()
        evidence = dict(
            self._load_verifications().get("artifacts", {}).get(candidate_id) or {}
        )
        same_file = (
            int(evidence.get("size_bytes", -1)) == int(stat.st_size)
            and int(evidence.get("mtime_ns", -1)) == int(stat.st_mtime_ns)
            and str(evidence.get("filename") or "") == candidate.filename
        )
        state = "present_unverified"
        verified = False
        actual_sha = ""
        if same_file:
            stored_state = str(evidence.get("state") or "")
            actual_sha = str(evidence.get("actual_sha256") or "")[:64]
            if stored_state in {
                "verified",
                "hash_mismatch",
                "verified_no_reference_hash",
            }:
                state = stored_state
                verified = stored_state == "verified"

        return {
            **base,
            "state": state,
            "present": True,
            "verified": verified,
            "ready_for_benchmark": verified,
            "size_bytes": int(stat.st_size),
            "verification_stale": bool(evidence) and not same_file,
            "actual_sha256": actual_sha,
            "verified_at": str(evidence.get("verified_at") or "") if same_file else "",
        }

    def verify_artifact(
        self,
        candidate_id: str,
        *,
        asset_root: str | Path | None = None,
    ) -> dict[str, Any]:
        candidate = self.get(candidate_id)
        if candidate is None:
            raise KeyError(candidate_id)
        path = self.artifact_path(candidate_id, asset_root=asset_root)
        if not path.exists() or not path.is_file():
            return self.artifact_status(candidate_id, asset_root=asset_root)

        stat = path.stat()
        actual = self._sha256_file(path)
        expected = candidate.sha256.lower()
        if expected:
            state = "verified" if actual == expected else "hash_mismatch"
        else:
            state = "verified_no_reference_hash"

        payload = self._load_verifications()
        artifacts = dict(payload.get("artifacts") or {})
        artifacts[candidate_id] = {
            "candidate_id": candidate_id,
            "filename": candidate.filename,
            "asset_group": self._asset_group(candidate),
            "size_bytes": int(stat.st_size),
            "mtime_ns": int(stat.st_mtime_ns),
            "actual_sha256": actual,
            "expected_sha256": expected,
            "state": state,
            "verified_at": self._now(),
        }
        payload["artifacts"] = artifacts
        self._save_verifications(payload)
        return self.artifact_status(candidate_id, asset_root=asset_root)

    def stack_status(
        self,
        *,
        base_candidate_id: str,
        adapter_candidate_ids: list[str] | tuple[str, ...] = (),
        asset_root: str | Path | None = None,
    ) -> dict[str, Any]:
        base_status = self.artifact_status(
            base_candidate_id,
            asset_root=asset_root,
        )
        adapters: list[dict[str, Any]] = []
        pairings: list[dict[str, Any]] = []
        for adapter_id in list(adapter_candidate_ids)[:16]:
            adapters.append(
                self.artifact_status(adapter_id, asset_root=asset_root)
            )
            pairings.append(
                self.compatibility(
                    base_candidate_id=base_candidate_id,
                    adapter_candidate_id=adapter_id,
                )
            )
        artifacts_verified = bool(base_status.get("verified")) and all(
            bool(item.get("verified")) for item in adapters
        )
        compatible = all(bool(item.get("directly_testable")) for item in pairings)
        return {
            "base": base_status,
            "adapters": adapters,
            "pairings": pairings,
            "artifacts_verified": artifacts_verified,
            "compatible": compatible,
            "ready_for_benchmark": bool(artifacts_verified and compatible),
            "ready_for_promotion": False,
            "policy": (
                "exact artifact hashes and exact base/runtime pairing are required "
                "before benchmarking; benchmark success still requires explicit promotion"
            ),
        }

    def snapshot(self) -> dict[str, Any]:
        rows: list[dict[str, Any]] = []
        for item in self.candidates.values():
            row = item.to_dict()
            if self.asset_root is not None:
                try:
                    row["artifact"] = self.artifact_status(item.candidate_id)
                except Exception:
                    row["artifact"] = {
                        "state": "inspection_failed",
                        "present": False,
                        "verified": False,
                        "ready_for_benchmark": False,
                    }
            rows.append(row)
        return {
            "version": self.VERSION,
            "path_present": bool(self.path and self.path.exists()),
            "count": len(self.candidates),
            "candidates": rows,
            "verification_store_present": bool(
                self.verification_path and self.verification_path.exists()
            ),
            "error": self.error,
            "policy": (
                "reviewed optional assets only; presence is not verification; "
                "verification is not runtime loading; benchmark is required before promotion"
            ),
        }
