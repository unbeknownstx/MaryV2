"""Prepare the next explicit Mary Dataset -> MLX experiment handoff.

This orchestrates existing canonical training/evaluation owners. It may write
Dataset v1, MLX data/config, and an execution plan, but it never installs
packages, downloads models, trains, benchmarks, registers an experiment, routes
traffic, or promotes a model.
"""
from __future__ import annotations

import argparse
import json
from pathlib import Path

from mary.core.config import Config
from mary.training import MaryCorpusMiner, inspect_mlx_bundle
from mary.training.mlx_bundle import PROFILES, prepare_mlx_bundle


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--root", type=Path, default=Path.cwd())
    parser.add_argument(
        "--output",
        type=Path,
        default=Path.home() / ".maryv2" / "training" / "mary-experiment-v1",
    )
    parser.add_argument("--profile", choices=sorted(PROFILES), default="m1-light")
    parser.add_argument("--feedback", type=Path, default=None)
    parser.add_argument("--novel-review", type=Path, default=None)
    args = parser.parse_args()

    root = args.root.expanduser().resolve()
    output = args.output.expanduser().resolve()

    feedback = args.feedback
    if feedback is None:
        candidate = (
            Path(Config.from_environment().paths.data)
            / "training"
            / "response_feedback.json"
        )
        feedback = candidate if candidate.exists() else None

    corpus = MaryCorpusMiner().inspect(root)
    manifest = prepare_mlx_bundle(
        root=root,
        output_dir=output,
        profile_id=args.profile,
        feedback_path=feedback,
        novel_review_path=args.novel_review,
    )
    preflight = inspect_mlx_bundle(output)

    candidate_path = output / "mary_adapter_candidate.json"
    plan = {
        "version": "mary-training-execution-plan-v1",
        "corpus": corpus.to_dict(),
        "dataset_fingerprint": manifest["dataset_fingerprint"],
        "profile": manifest["profile"],
        "examples": manifest["examples"],
        "dataset_audit": manifest["dataset_audit"],
        "training_readiness": manifest["training_readiness"],
        "host_preflight": preflight.to_dict(),
        "commands": {
            "preflight": manifest["run"]["preflight"],
            "train_explicit": manifest["run"]["train"],
            "evaluate_adapter_local": manifest["run"]["evaluate"],
            "propose_candidate_after_training": (
                f'python -m scripts.propose_mary_mlx_candidate '
                f'--bundle "{output}" --output "{candidate_path}"'
            ),
            "review_candidate_without_write": (
                f'python -m scripts.review_mlx_adapter_candidate "{candidate_path}"'
            ),
            "register_after_creator_approval": (
                f'python -m scripts.review_mlx_adapter_candidate '
                f'"{candidate_path}" --approve'
            ),
            "run_base_marybench": (
                f'python -m scripts.run_mary_mlx_marybench --bundle "{output}" '
                f'--variant base --output "{output / "marybench_base.json"}"'
            ),
            "run_adapter_marybench": (
                f'python -m scripts.run_mary_mlx_marybench --bundle "{output}" '
                f'--variant adapter --output "{output / "marybench_adapter.json"}"'
            ),
            "compare_marybench": (
                f'python -m scripts.compare_marybench_runs '
                f'"{output / "marybench_base.json"}" "{output / "marybench_adapter.json"}" '
                f'--output "{output / "marybench_scorecard.json"}"'
            ),
            "record_held_out_benchmark": (
                "python -m scripts.record_model_experiment_benchmark "
                "<experiment-id> marybench_scorecard.json --node-id <node-id> "
                "--artifact-fingerprint <artifact-fingerprint>"
            ),
            "sync_reviewed_benchmark_to_core": (
                "python -m scripts.sync_model_experiment_to_core <experiment-id>"
            ),
        },
        "gates": {
            "dataset_structurally_ready": bool(
                manifest["dataset_audit"]["training_ready"]
            ),
            "profile_dataset_ready": bool(
                manifest["training_readiness"]["dataset_ready"]
            ),
            "host_ready_for_training": preflight.ready_for_training,
            "adapter_present": preflight.adapter_present,
            "host_ready_for_adapter_evaluation": preflight.ready_for_evaluation,
            "manual_training_gate_required": True,
            "manual_candidate_review_required": True,
            "held_out_benchmark_required": True,
            "canonical_core_evidence_import_required": True,
            "manual_promotion_required": True,
        },
        "boundaries": {
            "ordinary_conversation_harvested": False,
            "marybench_used_for_training": False,
            "training_performed": False,
            "benchmark_performed": False,
            "experiment_registered": False,
            "runtime_routing_changed": False,
            "promotion_performed": False,
            "identity_or_memory_authority_granted": False,
        },
    }

    output.mkdir(parents=True, exist_ok=True)
    plan_path = output / "execution_plan.json"
    plan_path.write_text(
        json.dumps(plan, indent=2, ensure_ascii=False, sort_keys=True) + "\n",
        encoding="utf-8",
    )

    print("MARY TRAINING EXPERIMENT PREPARATION")
    print("=" * 64)
    print(f"corpus records:       {corpus.records}")
    print(f"structured behavior:  {corpus.structured_behavior_records}")
    print(f"held-out MaryBench:   {corpus.marybench_cases}")
    print(f"dataset fingerprint:  {manifest['dataset_fingerprint']}")
    print(f"profile:              {manifest['profile']['profile_id']}")
    print(f"train rows:           {manifest['examples']['train']}")
    print(
        "dataset ready:        "
        + ("YES" if manifest["training_readiness"]["dataset_ready"] else "NO")
    )
    print(
        "this host train ready: "
        + ("YES" if preflight.ready_for_training else "NO")
    )
    if preflight.blockers:
        for blocker in preflight.blockers:
            print(f"HOST BLOCKER: {blocker}")
    print(f"plan:                 {plan_path}")
    print(
        "No training, benchmark, registration, routing change, or promotion "
        "was performed."
    )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
