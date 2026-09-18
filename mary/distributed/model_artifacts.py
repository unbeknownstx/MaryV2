"""Node-local exact model/adapter artifact evidence.

This module bridges Mary's reviewed model candidate catalog to replaceable
capability nodes without turning local weights into Core authority.  It reports
only structural verification state: candidate IDs, exact hash verification,
base/adapter compatibility, and benchmark readiness.

A reachable runtime is not proof that a configured artifact is the reviewed
artifact; a verified artifact is not proof it is currently loaded; a benchmark
is still required before any promotion.
"""
from __future__ import annotations

import os
from pathlib import Path
from typing import Any, Iterable

from mary.core.config import PathConfig
from mary.learning import ModelCandidateCatalog


_MANIFEST = (
    Path(__file__).resolve().parents[2]
    / "assets"
    / "models"
    / "candidates"
    / "model_candidates.json"
)


def node_model_candidate_catalog(
    paths: PathConfig | None = None,
) -> ModelCandidateCatalog:
    active = paths or PathConfig()
    return ModelCandidateCatalog(
        _MANIFEST,
        asset_root=active.models,
        verification_path=active.runtime / "model_artifact_evidence.json",
    )


def summarize_model_stack(
    catalog: ModelCandidateCatalog,
    *,
    base_candidate_id: str,
    adapter_candidate_ids: Iterable[str] = (),
) -> dict[str, Any]:
    base_id = str(base_candidate_id or "").strip()
    adapters = tuple(
        dict.fromkeys(
            str(item or "").strip()
            for item in list(adapter_candidate_ids)[:16]
            if str(item or "").strip()
        )
    )
    if not base_id:
        return {
            "artifact_evidence_revision": 1,
            "artifact_configuration": "not_configured",
            "artifact_base_candidate": "",
            "artifact_state": "unknown",
            "artifact_verified": False,
            "artifact_adapter_count": len(adapters),
            "artifact_adapters_verified": 0,
            "artifact_stack_compatible": False,
            "artifact_ready_for_benchmark": False,
            "artifact_fingerprint": "",
        }
    try:
        stack = catalog.stack_status(
            base_candidate_id=base_id,
            adapter_candidate_ids=adapters,
        )
    except (KeyError, ValueError):
        return {
            "artifact_evidence_revision": 1,
            "artifact_configuration": "invalid_candidate",
            "artifact_base_candidate": base_id[:160],
            "artifact_state": "unknown",
            "artifact_verified": False,
            "artifact_adapter_count": len(adapters),
            "artifact_adapters_verified": 0,
            "artifact_stack_compatible": False,
            "artifact_ready_for_benchmark": False,
            "artifact_fingerprint": "",
        }

    base = dict(stack.get("base") or {})
    adapter_rows = list(stack.get("adapters") or [])
    fingerprint = str(base.get("actual_sha256") or "")[:16]
    return {
        "artifact_evidence_revision": 1,
        "artifact_configuration": "configured",
        "artifact_base_candidate": base_id[:160],
        "artifact_state": str(base.get("state") or "unknown")[:80],
        "artifact_verified": bool(base.get("verified")),
        "artifact_adapter_count": len(adapter_rows),
        "artifact_adapters_verified": sum(
            1 for item in adapter_rows if bool(dict(item).get("verified"))
        ),
        "artifact_stack_compatible": bool(stack.get("compatible")),
        "artifact_ready_for_benchmark": bool(stack.get("ready_for_benchmark")),
        "artifact_fingerprint": fingerprint,
    }


def model_artifact_metadata_from_environment(
    *,
    runtime: str,
    catalog: ModelCandidateCatalog | None = None,
) -> dict[str, Any]:
    name = str(runtime or "").strip().lower()
    if name != "llama.cpp":
        return summarize_model_stack(
            catalog or node_model_candidate_catalog(),
            base_candidate_id="",
        )

    base_id = os.getenv(
        "MARY_LLAMA_CPP_BASE_CANDIDATE_ID",
        "",
    ).strip()
    adapter_ids = tuple(
        item.strip()
        for item in os.getenv(
            "MARY_LLAMA_CPP_ADAPTER_CANDIDATE_IDS",
            "",
        ).split(",")
        if item.strip()
    )
    return summarize_model_stack(
        catalog or node_model_candidate_catalog(),
        base_candidate_id=base_id,
        adapter_candidate_ids=adapter_ids,
    )
