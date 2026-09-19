"""Explicitly copy one reviewed model experiment's content-free evidence into Mary Core.

Run this from the machine that owns the reviewed local experiment ledger after
benchmarking. The authenticated Core import preserves the deterministic
experiment id and benchmark metadata, but never copies prompts/generated text,
changes production routing, or promotes a model.
"""
from __future__ import annotations

import argparse
import json
import os
from pathlib import Path

from dotenv import load_dotenv

from mary.core.config import PathConfig
from mary.learning import ModelExperimentLedger
from mary.protocol.client import MaryClient


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument(
        "experiment_id",
        nargs="?",
        default="",
        help="Defaults to MARY_MLX_EXPERIMENT_ID then MARY_MODEL_EXPERIMENT_ID.",
    )
    parser.add_argument(
        "--ledger",
        type=Path,
        default=None,
        help="Local experiment ledger; defaults to MARY_MODEL_EXPERIMENT_LEDGER or PathConfig runtime.",
    )
    parser.add_argument("--core-url", default="")
    parser.add_argument("--core-token", default="")
    args = parser.parse_args()

    load_dotenv(override=False)
    experiment_id = (
        str(args.experiment_id or "").strip()
        or os.getenv("MARY_MLX_EXPERIMENT_ID", "").strip()
        or os.getenv("MARY_MODEL_EXPERIMENT_ID", "").strip()
    )
    if not experiment_id:
        raise SystemExit(
            "experiment_id is required (argument, MARY_MLX_EXPERIMENT_ID, "
            "or MARY_MODEL_EXPERIMENT_ID)"
        )

    ledger_path = args.ledger
    if ledger_path is None:
        configured = os.getenv("MARY_MODEL_EXPERIMENT_LEDGER", "").strip()
        ledger_path = (
            Path(configured).expanduser()
            if configured
            else PathConfig().runtime / "model_experiment_evidence.json"
        )
    ledger = ModelExperimentLedger(ledger_path)
    evidence = ledger.export_portable_evidence(experiment_id)

    core_url = str(args.core_url or os.getenv("MARY_CORE_URL", "")).strip()
    core_token = str(args.core_token or os.getenv("MARY_CORE_TOKEN", "")).strip()
    if not core_url or not core_token:
        raise SystemExit(
            "MARY_CORE_URL and MARY_CORE_TOKEN are required for canonical Core import."
        )

    client = MaryClient(
        core_url,
        token=core_token,
        device_id="model-experiment-evidence-sync",
        surface="experiment_lab",
        timeout=30,
    )
    result = client.runtime_action(
        "model.experiment.import_evidence",
        {"evidence": evidence},
    )

    experiment = dict(result.get("experiment") or {})
    nodes = list(result.get("nodes") or [])
    print("MARY MODEL EXPERIMENT CORE SYNC")
    print("=" * 64)
    print(f"experiment:       {experiment.get('id')}")
    print(f"state:            {experiment.get('status')}")
    print(f"benchmark:        {experiment.get('benchmark_verified')}")
    print(f"trial ready:      {experiment.get('trial_ready')}")
    print(f"dataset:          {experiment.get('dataset_fingerprint')}")
    print(f"matching nodes:   {len(nodes)}")
    print(
        "No prompts/generated output were transferred; no routing or promotion "
        "was performed."
    )
    print(json.dumps(
        {
            "core_registration_present": result.get("core_registration_present"),
            "promotion_performed": result.get("promotion_performed"),
            "production_route_changed": result.get("production_route_changed"),
            "nodes": nodes,
        },
        indent=2,
        ensure_ascii=False,
    ))
    return 0 if bool(result.get("core_registration_present")) else 2


if __name__ == "__main__":
    raise SystemExit(main())
