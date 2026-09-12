"""Export Mary's creator-authored evaluation set for external experiment tools."""
from __future__ import annotations

import argparse
from pathlib import Path

from mary.character import MaryEvaluationSet
from mary.learning.interop import records_from_evaluation_set, write_bundle


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description="Export proposal-only MaryBench interoperability bundle.")
    parser.add_argument(
        "--output",
        type=Path,
        default=Path.home() / ".maryv2" / "labs" / "marybench_13_14.json",
    )
    args = parser.parse_args(argv)
    suite = MaryEvaluationSet.from_environment()
    rows = records_from_evaluation_set(suite)
    summary = write_bundle(args.output.expanduser(), rows)
    print("MARYV2 13.14 MARYBENCH EXPORT")
    print("=" * 64)
    print(f"cases:  {summary['records']}")
    print(f"output: {summary['path']}")
    print("policy: evaluation/optimization input only; no automatic Mary mutation")
    if not rows:
        print("No evaluation cases are configured. Set MARY_CHARACTER_EVALS or add the canonical evaluation file.")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
