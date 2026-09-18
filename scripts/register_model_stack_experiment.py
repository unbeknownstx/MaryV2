"""Register an already SHA-verified local model/adapter stack for benchmarking."""
from __future__ import annotations

import argparse
import json

from mary.core.config import PathConfig
from mary.distributed.model_artifacts import node_model_candidate_catalog, summarize_model_stack
from mary.learning import ModelExperimentLedger


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--base-candidate", required=True)
    parser.add_argument("--adapter-candidate", action="append", default=[])
    parser.add_argument("--candidate-id", default="")
    parser.add_argument("--reviewed-by", default="creator")
    args = parser.parse_args()

    catalog = node_model_candidate_catalog()
    stack = summarize_model_stack(
        catalog,
        base_candidate_id=args.base_candidate,
        adapter_candidate_ids=args.adapter_candidate,
    )
    if not stack.get("artifact_ready_for_benchmark"):
        raise SystemExit(
            "stack is not ready for benchmark; verify exact artifact hashes and compatibility first"
        )
    base = catalog.get(args.base_candidate)
    if base is None:
        raise SystemExit("base candidate is missing")
    candidate_id = args.candidate_id.strip() or (
        "stack-" + args.base_candidate + (
            "-" + "-".join(args.adapter_candidate) if args.adapter_candidate else ""
        )
    )
    ledger = ModelExperimentLedger(
        PathConfig().runtime / "model_experiment_evidence.json"
    )
    record = ledger.register_verified_stack(
        candidate_id=candidate_id,
        runtime=base.runtime,
        model=base.repository,
        upstream_base=base.upstream_base or base.repository,
        base_candidate_id=base.candidate_id,
        adapter_candidate_ids=args.adapter_candidate,
        artifact_fingerprint=str(stack.get("artifact_fingerprint") or ""),
        reviewed_by=args.reviewed_by,
        notes=("exact candidate catalog hashes verified",),
    )
    print(json.dumps(record.to_dict(), indent=2, ensure_ascii=False))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
