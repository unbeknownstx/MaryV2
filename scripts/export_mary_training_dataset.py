"""Export Mary's explicit creator-rated training/evaluation dataset.

This never scrapes conversation history. It reads only the private
response-feedback store created through explicit rating/correction actions.
"""
from __future__ import annotations

import argparse
from pathlib import Path

from mary.core.config import Config
from mary.training import MaryTrainingDatasetExporter, ResponseFeedbackStore


def main() -> int:
    parser = argparse.ArgumentParser(description="Export explicit Mary feedback into JSONL datasets.")
    parser.add_argument("--feedback", default="", help="Optional path to response_feedback.json")
    parser.add_argument("--output", default="mary_training_export", help="Output directory")
    args = parser.parse_args()

    config = Config.from_environment()
    feedback_path = (
        Path(args.feedback).expanduser().resolve()
        if str(args.feedback).strip()
        else Path(config.paths.data) / "training" / "response_feedback.json"
    )
    store = ResponseFeedbackStore(feedback_path)
    exporter = MaryTrainingDatasetExporter()
    summary = exporter.export(store, Path(args.output))

    print("MARYV2 EXPLICIT TRAINING DATASET EXPORT")
    print("=" * 64)
    print(f"Feedback source: {feedback_path}")
    print(f"Source records: {summary.source_records}")
    print(f"SFT examples:   {summary.sft}")
    print(f"Preferences:    {summary.preferences}")
    print(f"Rejected:       {summary.rejected}")
    print(f"Eval examples:  {summary.eval}")
    print(f"Output:         {summary.output_dir}")
    print("Policy: explicit feedback only; no ordinary chat harvesting; no training performed.")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
