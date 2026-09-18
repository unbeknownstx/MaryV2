"""Record held-out model experiment scores against one exact artifact fingerprint."""
from __future__ import annotations

import argparse
import json
from pathlib import Path

from mary.core.config import PathConfig
from mary.learning import ModelExperimentLedger


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("experiment_id")
    parser.add_argument("scores_json", type=Path)
    parser.add_argument("--node-id", required=True)
    parser.add_argument("--artifact-fingerprint", required=True)
    parser.add_argument("--latency-ms", type=float, default=None)
    parser.add_argument("--source", default="marybench")
    args = parser.parse_args()

    payload = json.loads(args.scores_json.expanduser().read_text(encoding="utf-8"))
    scores = dict(payload.get("scores") or payload)
    ledger = ModelExperimentLedger(
        PathConfig().runtime / "model_experiment_evidence.json"
    )
    record = ledger.record_benchmark(
        args.experiment_id,
        node_id=args.node_id,
        artifact_fingerprint=args.artifact_fingerprint,
        scores=scores,
        latency_ms=args.latency_ms,
        benchmark_source=args.source,
    )
    print(json.dumps(record.to_dict(), indent=2, ensure_ascii=False))
    return 0 if record.benchmark_verified else 2


if __name__ == "__main__":
    raise SystemExit(main())
