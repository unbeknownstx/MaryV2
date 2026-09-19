"""Inspect Mary's active creator-owned character corpus before training."""
from __future__ import annotations

import argparse
import json
from pathlib import Path

from mary.training.corpus_mining import MaryCorpusMiner


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--root", type=Path, default=Path.cwd())
    parser.add_argument("--json", action="store_true")
    args = parser.parse_args()

    report = MaryCorpusMiner().inspect(args.root)
    payload = report.to_dict()
    if args.json:
        print(json.dumps(payload, indent=2, ensure_ascii=False, sort_keys=True))
        return 0

    print("=" * 64)
    print("MARY CORPUS MINING INVENTORY")
    print("=" * 64)
    print(f"fingerprint:              {report.fingerprint}")
    print(f"sourcebook records:       {report.records}")
    print(f"sources:                  {report.sources}")
    print(f"structured behavior:      {report.structured_behavior_records}")
    print(f"training candidates:      {report.training_candidate_records}")
    print(f"negative examples:        {report.negative_records}")
    print(f"fiction references:       {report.fictional_reference_records}")
    print(f"exact duplicate groups:   {report.duplicate_content_groups}")
    print(f"MaryBench cases:          {report.marybench_cases}")
    print(f"dominant source share:    {report.dominant_source_share:.1%}")
    for item in report.recommendations:
        print(f"REVIEW: {item}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
