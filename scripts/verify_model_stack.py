"""Verify exact local base/LoRA artifacts before Adapter Lab benchmarking."""
from __future__ import annotations

import argparse
import json
from pathlib import Path

from mary.distributed.model_artifacts import node_model_candidate_catalog


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--base", required=True, help="reviewed base candidate id")
    parser.add_argument(
        "--adapter",
        action="append",
        default=[],
        help="reviewed LoRA candidate id; repeat for multiple adapters",
    )
    parser.add_argument(
        "--asset-root",
        type=Path,
        default=None,
        help="override the normal Mary model root for this verification",
    )
    args = parser.parse_args(argv)

    catalog = node_model_candidate_catalog()
    ids = [args.base, *args.adapter]
    results = []
    for candidate_id in ids:
        results.append(
            catalog.verify_artifact(
                candidate_id,
                asset_root=args.asset_root,
            )
        )

    stack = catalog.stack_status(
        base_candidate_id=args.base,
        adapter_candidate_ids=args.adapter,
        asset_root=args.asset_root,
    )
    print(json.dumps(
        {
            "verified_artifacts": results,
            "stack": stack,
            "next_step": (
                "run a blinded Adapter Lab benchmark"
                if stack["ready_for_benchmark"]
                else "repair artifact verification or base/adapter compatibility"
            ),
        },
        indent=2,
        ensure_ascii=False,
    ))
    return 0 if stack["ready_for_benchmark"] else 2


if __name__ == "__main__":
    raise SystemExit(main())
