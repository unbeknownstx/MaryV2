"""Content-free reproducibility lineage for prepared Mary MLX bundles.

The lineage fingerprint binds the exact prepared training split, held-out test
split, training profile, Dataset v1 fingerprint, sourcebook hash, MaryBench
fingerprint, and optional reviewed-novel provenance without storing any source
text in the durable experiment ledger.
"""
from __future__ import annotations

from dataclasses import asdict, dataclass
from hashlib import sha256
import json
from pathlib import Path
from typing import Any


def _sha256(path: Path) -> str:
    digest = sha256()
    with path.open("rb") as handle:
        for chunk in iter(lambda: handle.read(1024 * 1024), b""):
            digest.update(chunk)
    return digest.hexdigest()


def _canonical_hash(payload: Any) -> str:
    encoded = json.dumps(
        payload,
        ensure_ascii=False,
        sort_keys=True,
        separators=(",", ":"),
    ).encode("utf-8")
    return sha256(encoded).hexdigest()


@dataclass(frozen=True)
class MlxBundleLineage:
    version: str
    bundle_fingerprint: str
    dataset_fingerprint: str
    profile_fingerprint: str
    train_sha256: str
    validation_sha256: str
    test_sha256: str
    sourcebook_hash: str
    marybench_fingerprint: str
    novel_review_sha256: str
    feedback_records: int
    missing_files: tuple[str, ...]

    def to_dict(self) -> dict[str, Any]:
        payload = asdict(self)
        payload["missing_files"] = list(self.missing_files)
        payload["content_included"] = False
        payload["training_performed"] = False
        payload["authority"] = "pretraining_lineage_only"
        return payload


def build_mlx_bundle_lineage(bundle: str | Path) -> MlxBundleLineage:
    """Build a machine/path-independent fingerprint for a prepared MLX bundle."""

    root = Path(bundle).expanduser().resolve()
    manifest_path = root / "manifest.json"
    dataset_manifest_path = root / "mary-dataset-v1" / "manifest.json"
    if not manifest_path.exists():
        raise FileNotFoundError(f"Mary MLX bundle manifest not found: {manifest_path}")
    if not dataset_manifest_path.exists():
        raise FileNotFoundError(
            f"Mary Dataset v1 manifest not found: {dataset_manifest_path}"
        )

    manifest = json.loads(manifest_path.read_text(encoding="utf-8"))
    dataset_manifest = json.loads(dataset_manifest_path.read_text(encoding="utf-8"))
    if not isinstance(manifest, dict) or not isinstance(dataset_manifest, dict):
        raise ValueError("Mary bundle manifests must be JSON objects")

    profile = dict(manifest.get("profile") or {})
    dataset_fingerprint = str(
        manifest.get("dataset_fingerprint")
        or dict(manifest.get("mary_dataset") or {}).get("fingerprint")
        or dataset_manifest.get("fingerprint")
        or ""
    )[:160]
    sources = dict(dataset_manifest.get("sources") or {})
    sourcebook = dict(sources.get("sourcebook") or {})
    marybench = dict(sources.get("marybench") or {})
    novel = dict(sources.get("reviewed_novel_behavior") or {})
    feedback = dict(sources.get("explicit_feedback") or {})

    split_paths = {
        "train": root / "mlx-data" / "train.jsonl",
        "validation": root / "mlx-data" / "valid.jsonl",
        "test": root / "mlx-data" / "test.jsonl",
    }
    missing = tuple(
        name for name, path in split_paths.items() if not path.exists()
    )
    split_hashes = {
        name: (_sha256(path) if path.exists() else "")
        for name, path in split_paths.items()
    }

    profile_fingerprint = _canonical_hash(profile)
    lineage_payload = {
        "version": "mary-mlx-bundle-lineage-v1",
        "dataset_fingerprint": dataset_fingerprint,
        "profile_fingerprint": profile_fingerprint,
        "splits": split_hashes,
        "sourcebook_hash": str(sourcebook.get("hash") or "")[:160],
        "marybench_fingerprint": str(marybench.get("fingerprint") or "")[:160],
        "novel_review_sha256": str(novel.get("sha256") or "")[:64],
        "feedback_records": int(feedback.get("source_records") or 0),
        "missing_files": list(missing),
    }
    bundle_fingerprint = _canonical_hash(lineage_payload)

    return MlxBundleLineage(
        version="mary-mlx-bundle-lineage-v1",
        bundle_fingerprint=bundle_fingerprint,
        dataset_fingerprint=dataset_fingerprint,
        profile_fingerprint=profile_fingerprint,
        train_sha256=split_hashes["train"],
        validation_sha256=split_hashes["validation"],
        test_sha256=split_hashes["test"],
        sourcebook_hash=str(sourcebook.get("hash") or "")[:160],
        marybench_fingerprint=str(marybench.get("fingerprint") or "")[:160],
        novel_review_sha256=str(novel.get("sha256") or "")[:64],
        feedback_records=int(feedback.get("source_records") or 0),
        missing_files=missing,
    )
