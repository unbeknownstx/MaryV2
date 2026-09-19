"""Compare base and Mary-adapter local MaryBench runs.

The output deliberately leaves semantic acceptance scores blank. Deterministic
anti-pattern checks are evidence for review, not a substitute for judging Mary
likeness, naturalism, context adherence or boundary quality.
"""
from __future__ import annotations

import argparse
import json
from pathlib import Path

from mary.training.marybench_experiment import comparison_scorecard


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("base", type=Path)
    parser.add_argument("adapter", type=Path)
    parser.add_argument("--output", type=Path, required=True)
    args = parser.parse_args()

    base = json.loads(args.base.expanduser().read_text(encoding="utf-8"))
    adapter = json.loads(args.adapter.expanduser().read_text(encoding="utf-8"))
    scorecard = comparison_scorecard(base, adapter)

    target = args.output.expanduser().resolve()
    target.parent.mkdir(parents=True, exist_ok=True)
    target.write_text(
        json.dumps(scorecard, indent=2, ensure_ascii=False, sort_keys=True) + "\n",
        encoding="utf-8",
    )

    delta = dict(scorecard.get("delta") or {})
    print("MARYBENCH BASE VS ADAPTER")
    print("=" * 64)
    print(f"benchmark:          {scorecard['benchmark_fingerprint']}")
    print(f"cases:              {scorecard['benchmark_case_count']}")
    print(
        "guardrail delta:    "
        f"{float(delta.get('deterministic_pass_rate') or 0.0):+.1%}"
    )
    if delta.get("mean_latency_ms") is not None:
        print(f"latency delta:      {float(delta['mean_latency_ms']):+.2f} ms")
    print(f"review scorecard:   {target}")
    print(
        "Fill the semantic scores after review; this command does not register "
        "a benchmark or promote the adapter."
    )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
