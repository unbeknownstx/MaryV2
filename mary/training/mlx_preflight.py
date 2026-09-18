"""Deterministic preflight for a prepared Mary MLX adapter bundle.

This module performs no downloads, installs, training, inference or model
promotion. It verifies that a prepared bundle is internally consistent and that
an Apple-Silicon host has the local Python packages needed to execute the
explicit MLX-LM commands recorded in the bundle.
"""
from __future__ import annotations

from dataclasses import asdict, dataclass
import importlib.util
import json
from pathlib import Path
import platform
from typing import Any


@dataclass(frozen=True)
class MlxBundlePreflight:
    bundle: str
    profile_id: str
    model: str
    upstream_base: str
    host_system: str
    host_machine: str
    apple_silicon: bool
    mlx_available: bool
    mlx_lm_available: bool
    train_examples: int
    minimum_train_examples: int
    dataset_ready: bool
    config_lineage_matches: bool
    adapter_present: bool
    adapter_lineage_matches: bool | None
    ready_for_training: bool
    ready_for_evaluation: bool
    blockers: tuple[str, ...]
    warnings: tuple[str, ...]

    def to_dict(self) -> dict[str, Any]:
        payload = asdict(self)
        payload["blockers"] = list(self.blockers)
        payload["warnings"] = list(self.warnings)
        return payload


def _count_jsonl(path: Path) -> int:
    if not path.exists():
        return 0
    return sum(1 for line in path.read_text(encoding="utf-8").splitlines() if line.strip())


def _package_available(name: str) -> bool:
    try:
        return importlib.util.find_spec(name) is not None
    except (ImportError, AttributeError, ValueError):
        return False


def inspect_mlx_bundle(
    bundle: str | Path,
    *,
    host_system: str | None = None,
    host_machine: str | None = None,
    mlx_available: bool | None = None,
    mlx_lm_available: bool | None = None,
) -> MlxBundlePreflight:
    root = Path(bundle).expanduser().resolve()
    manifest_path = root / "manifest.json"
    if not manifest_path.exists():
        raise FileNotFoundError(f"Mary MLX bundle manifest not found: {manifest_path}")

    raw = json.loads(manifest_path.read_text(encoding="utf-8"))
    if not isinstance(raw, dict):
        raise ValueError("Mary MLX bundle manifest must be a JSON object")

    profile = dict(raw.get("profile") or {})
    profile_id = str(profile.get("profile_id") or "")
    model = str(profile.get("model") or "")
    upstream_base = str(profile.get("upstream_base") or "")
    minimum = max(1, int(profile.get("minimum_train_examples") or 1))

    data_dir = root / "mlx-data"
    train_examples = _count_jsonl(data_dir / "train.jsonl")
    dataset_ready = train_examples >= minimum

    config_path = root / "mlx_lora_config.yaml"
    config_text = (
        config_path.read_text(encoding="utf-8")
        if config_path.exists()
        else ""
    )
    config_lineage_matches = bool(
        model and f'model: "{model}"' in config_text
    )

    system = str(host_system if host_system is not None else platform.system())
    machine = str(host_machine if host_machine is not None else platform.machine())
    apple_silicon = (
        system.casefold() == "darwin"
        and machine.casefold() in {"arm64", "aarch64"}
    )
    has_mlx = _package_available("mlx") if mlx_available is None else bool(mlx_available)
    has_mlx_lm = (
        _package_available("mlx_lm")
        if mlx_lm_available is None
        else bool(mlx_lm_available)
    )

    adapter_dir = root / "adapter"
    adapter_config = adapter_dir / "adapter_config.json"
    adapter_weights = adapter_dir / "adapters.safetensors"
    adapter_present = adapter_config.exists() and adapter_weights.exists()
    adapter_lineage_matches: bool | None = None
    warnings: list[str] = []
    if adapter_present:
        try:
            adapter_raw = json.loads(adapter_config.read_text(encoding="utf-8"))
            adapter_lineage_matches = (
                isinstance(adapter_raw, dict)
                and str(adapter_raw.get("model") or "") == model
                and str(adapter_raw.get("fine_tune_type") or "lora") in {"lora", "dora"}
            )
        except (OSError, json.JSONDecodeError):
            adapter_lineage_matches = False
    else:
        warnings.append(
            "No trained adapter is present yet; evaluation readiness is false until "
            "MLX-LM writes adapter_config.json and adapters.safetensors."
        )

    blockers: list[str] = []
    if not apple_silicon:
        blockers.append("Mary's MLX training path requires macOS on Apple Silicon.")
    if not has_mlx:
        blockers.append("Python package 'mlx' is not available.")
    if not has_mlx_lm:
        blockers.append("Python package 'mlx_lm' is not available.")
    if not dataset_ready:
        blockers.append(
            f"Approved training set has {train_examples} row(s); "
            f"profile requires at least {minimum}."
        )
    if not config_lineage_matches:
        blockers.append("Generated MLX config does not pin the manifest's exact model lineage.")

    ready_for_training = not blockers
    ready_for_evaluation = bool(
        ready_for_training
        and adapter_present
        and adapter_lineage_matches is True
    )
    if adapter_present and adapter_lineage_matches is False:
        warnings.append(
            "Adapter files exist but adapter_config.json does not match the exact "
            "bundle model/fine-tune lineage; do not load or evaluate them."
        )

    return MlxBundlePreflight(
        bundle=str(root),
        profile_id=profile_id,
        model=model,
        upstream_base=upstream_base,
        host_system=system,
        host_machine=machine,
        apple_silicon=apple_silicon,
        mlx_available=has_mlx,
        mlx_lm_available=has_mlx_lm,
        train_examples=train_examples,
        minimum_train_examples=minimum,
        dataset_ready=dataset_ready,
        config_lineage_matches=config_lineage_matches,
        adapter_present=adapter_present,
        adapter_lineage_matches=adapter_lineage_matches,
        ready_for_training=ready_for_training,
        ready_for_evaluation=ready_for_evaluation,
        blockers=tuple(blockers),
        warnings=tuple(warnings),
    )
