"""Prepare a creator-review template from a Mary novel-mining bundle.

The template intentionally omits raw scene text. It carries provenance and blank
behavior-abstraction fields so fictional plot is not accidentally converted
into AI-Mary memory or direct SFT without creator authorship/review.
"""
from __future__ import annotations

import argparse
import json
from pathlib import Path


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("mining_bundle", type=Path)
    parser.add_argument("output", type=Path)
    parser.add_argument("--limit", type=int, default=250)
    args = parser.parse_args()

    source = args.mining_bundle.expanduser().resolve()
    payload = json.loads(source.read_text(encoding="utf-8"))
    source_meta = dict(payload.get("source") or {})
    reviews = []
    for item in list(payload.get("candidates") or [])[: max(1, min(2000, int(args.limit)))]:
        if not isinstance(item, dict):
            continue
        reviews.append({
            "candidate_id": str(item.get("candidate_id") or ""),
            "chapter": str(item.get("chapter") or ""),
            "source_file": str(item.get("source_file") or source_meta.get("file") or ""),
            "source_sha256": str(item.get("source_sha256") or source_meta.get("sha256") or ""),
            "status": "pending",
            "situation": "",
            "mary_behavior": "",
            "avoid": "",
            "tags": [],
            "review_note": (
                "Abstract only a recurring Mary behavior/reaction/cadence that "
                "generalizes beyond the fictional plot."
            ),
        })

    target = args.output.expanduser().resolve()
    target.parent.mkdir(parents=True, exist_ok=True)
    target.write_text(json.dumps({
        "version": "mary-novel-behavior-review-v1",
        "source": source_meta,
        "boundaries": {
            "raw_excerpt_included": False,
            "fiction_is_ai_memory": False,
            "approved_rows_only_enter_dataset": True,
        },
        "reviews": reviews,
    }, indent=2, ensure_ascii=False, sort_keys=True), encoding="utf-8")
    print(f"Prepared {len(reviews)} review rows at {target}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
