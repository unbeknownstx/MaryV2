"""Verify exact local base/LoRA artifacts before Adapter Lab benchmarking."""
from __future__ import annotations

import argparse
import json
from pathlib import Path

from mary.distributed.model_artifacts import node_model_candidate_catalog


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument(
        "--base",
        default="",
        help="reviewed base candidate id; omit for offline structural verification",
    )
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
    if not args.base:
        snapshot = dict(catalog.snapshot() or {})
        candidates = list(snapshot.get("candidates") or [])
        invalid = [
            item
            for item in candidates
            if not str(item.get("id") or "").strip()
            or not str(item.get("runtime") or "").strip()
            or not str(item.get("repository") or "").strip()
        ]
        payload = {
            "ok": bool(candidates) and not invalid,
            "mode": "offline_structural",
            "candidate_count": len(candidates),
            "invalid_candidates": len(invalid),
            "downloads": False,
            "artifact_reads_required": False,
            "authority": "verification_only",
        }
        print(json.dumps(payload, indent=2, ensure_ascii=False))
        return 0 if payload["ok"] else 2

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
