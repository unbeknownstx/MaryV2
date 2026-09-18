"""Review and register one trained MLX adapter as an experiment candidate.

No model is loaded and no production route changes. Without --approve this is a
read-only preview.
"""
from __future__ import annotations

import argparse
import json
from pathlib import Path

from mary.core.config import PathConfig
from mary.learning import ModelExperimentLedger


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("proposal", type=Path)
    parser.add_argument("--approve", action="store_true")
    parser.add_argument("--reviewed-by", default="creator")
    args = parser.parse_args()

    payload = json.loads(args.proposal.expanduser().read_text(encoding="utf-8"))
    if not args.approve:
        print(json.dumps({
            "candidate_id": payload.get("candidate_id"),
            "runtime": payload.get("runtime"),
            "model": payload.get("model"),
            "upstream_base": payload.get("upstream_base"),
            "status": "review_required",
            "write_performed": False,
            "next": "rerun with --approve after reviewing exact lineage and hashes",
        }, indent=2))
        return 0

    ledger = ModelExperimentLedger(
        PathConfig().runtime / "model_experiment_evidence.json"
    )
    record = ledger.register_mlx_proposal(
        payload,
        reviewed_by=args.reviewed_by,
    )
    print(json.dumps(record.to_dict(), indent=2, ensure_ascii=False))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
