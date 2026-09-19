"""Build a review-only candidate handoff from a trained Mary MLX adapter.

The handoff hashes local adapter artifacts and records exact lineage. It does not
modify the model candidate catalog, load a model, route traffic, or promote an
adapter into Mary's runtime.
"""
from __future__ import annotations

from dataclasses import asdict, dataclass
from hashlib import sha256
import json
from pathlib import Path
from typing import Any

from .mlx_preflight import inspect_mlx_bundle


def _sha256(path: Path) -> str:
    digest = sha256()
    with path.open("rb") as handle:
        while True:
            chunk = handle.read(1024 * 1024)
            if not chunk:
                break
            digest.update(chunk)
    return digest.hexdigest()


@dataclass(frozen=True)
class MlxAdapterCandidateProposal:
    version: str
    status: str
    candidate_id: str
    profile_id: str
    runtime: str
    model: str
    upstream_base: str
    adapter_config_sha256: str
    adapter_weights_sha256: str
    adapter_weights_bytes: int
    dataset_fingerprint: str
    experiment_class: str
    benchmark_required: bool
    catalog_write_performed: bool
    runtime_load_performed: bool
    promotion_performed: bool
    notes: tuple[str, ...]

    def to_dict(self) -> dict[str, Any]:
        payload = asdict(self)
        payload["notes"] = list(self.notes)
        return payload


def build_mlx_adapter_candidate_proposal(
    bundle: str | Path,
    *,
    candidate_id: str = "",
    host_system: str | None = None,
    host_machine: str | None = None,
    mlx_available: bool | None = None,
    mlx_lm_available: bool | None = None,
) -> MlxAdapterCandidateProposal:
    root = Path(bundle).expanduser().resolve()
    report = inspect_mlx_bundle(
        root,
        host_system=host_system,
        host_machine=host_machine,
        mlx_available=mlx_available,
        mlx_lm_available=mlx_lm_available,
    )
    if not report.ready_for_evaluation:
        raise ValueError(
            "MLX adapter bundle is not ready for candidate handoff: "
            + "; ".join(report.blockers or report.warnings)
        )

    manifest = json.loads((root / "manifest.json").read_text(encoding="utf-8"))
    profile = dict(manifest.get("profile") or {})
    adapter_dir = root / "adapter"
    config_path = adapter_dir / "adapter_config.json"
    weights_path = adapter_dir / "adapters.safetensors"

    clean_id = str(candidate_id or "").strip()
    if not clean_id:
        clean_id = (
            "mary-"
            + str(report.profile_id or "mlx").replace("_", "-").replace(" ", "-").casefold()
            + "-adapter"
        )
    clean_id = "".join(
        ch for ch in clean_id[:120]
        if ch.isalnum() or ch in {"-", "_", "."}
    )
    if not clean_id:
        raise ValueError("candidate_id is invalid")

    mary_dataset = dict(manifest.get("mary_dataset") or {})
    dataset_fingerprint = str(
        manifest.get("dataset_fingerprint")
        or manifest.get("source_dataset_fingerprint")
        or mary_dataset.get("fingerprint")
        or ""
    )[:160]
    if not dataset_fingerprint:
        raise ValueError(
            "MLX adapter bundle is missing Mary Dataset fingerprint lineage"
        )

    return MlxAdapterCandidateProposal(
        version="mary-mlx-adapter-candidate-v1",
        status="review_required",
        candidate_id=clean_id,
        profile_id=report.profile_id,
        runtime="mlx_lm",
        model=report.model,
        upstream_base=report.upstream_base,
        adapter_config_sha256=_sha256(config_path),
        adapter_weights_sha256=_sha256(weights_path),
        adapter_weights_bytes=weights_path.stat().st_size,
        dataset_fingerprint=dataset_fingerprint,
        experiment_class=str(profile.get("experiment_class") or "unknown")[:120],
        benchmark_required=True,
        catalog_write_performed=False,
        runtime_load_performed=False,
        promotion_performed=False,
        notes=(
            "Exact base lineage must remain unchanged.",
            "Benchmark base-only versus adapter under held-out MaryBench before promotion.",
            "This proposal is local artifact evidence only and grants no Mary authority.",
        ),
    )
