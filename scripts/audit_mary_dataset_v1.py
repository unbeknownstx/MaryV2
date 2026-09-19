"""Audit an exported Mary Dataset v1 bundle before LoRA preparation."""
from __future__ import annotations

import argparse
import json
from pathlib import Path

from mary.training.dataset_audit import MaryDatasetV1Auditor


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument(
        "--dataset",
        type=Path,
        default=Path.home() / ".maryv2" / "datasets" / "mary-dataset-v1",
    )
    parser.add_argument("--json", action="store_true")
    parser.add_argument("--minimum-train-examples", type=int, default=8)
    args = parser.parse_args()

    report = MaryDatasetV1Auditor().audit(
        args.dataset,
        minimum_train_examples=args.minimum_train_examples,
    )
    payload = report.to_dict()
    if args.json:
        print(json.dumps(payload, indent=2, ensure_ascii=False, sort_keys=True))
    else:
        print("=" * 64)
        print("MARY DATASET V1 QUALITY AUDIT")
        print("=" * 64)
        print(f"fingerprint:       {report.dataset_fingerprint or 'missing'}")
        print(f"training rows:     {report.training_rows}")
        print(f"train/valid/test:  {report.train_rows}/{report.validation_rows}/{report.test_rows}")
        print(f"duplicates:        {report.duplicate_groups}")
        print(f"split leakage:     {report.split_leakage_groups}")
        print(f"MaryBench leaks:   {report.marybench_prompt_leaks}")
        print(f"boundary issues:   {report.boundary_violations}")
        print(f"training ready:    {'YES' if report.training_ready else 'NO'}")
        for item in report.blocking_issues:
            print(f"BLOCK: {item}")
        for item in report.warnings:
            print(f"WARN:  {item}")
    return 0 if report.training_ready else 2


if __name__ == "__main__":
    raise SystemExit(main())
