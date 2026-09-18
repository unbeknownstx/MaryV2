"""Export Mary Dataset v1 from approved character/evaluation/feedback material."""
from __future__ import annotations

import argparse
from pathlib import Path

from mary.core.config import Config
from mary.training import MaryDatasetV1Exporter


def main() -> int:
    parser = argparse.ArgumentParser(
        description="Export provenance-bearing Mary Dataset v1 without harvesting ordinary chats."
    )
    parser.add_argument(
        "--root",
        type=Path,
        default=Path.cwd(),
        help="MaryV2 checkout root used to discover approved character sources/evals.",
    )
    parser.add_argument(
        "--output",
        type=Path,
        default=Path.home() / ".maryv2" / "datasets" / "mary-dataset-v1",
        help="Output directory.",
    )
    parser.add_argument(
        "--feedback",
        type=Path,
        default=None,
        help="Optional explicit response_feedback.json. Defaults to configured Mary data root if present.",
    )
    parser.add_argument(
        "--novel-review",
        type=Path,
        default=None,
        help=(
            "Optional creator-reviewed novel behavior JSON. Only approved "
            "abstract situation/behavior rows enter SFT."
        ),
    )
    args = parser.parse_args()

    config = Config.from_environment()
    feedback = args.feedback
    if feedback is None:
        candidate = Path(config.paths.data) / "training" / "response_feedback.json"
        feedback = candidate if candidate.exists() else None

    summary = MaryDatasetV1Exporter().export(
        root=args.root,
        output_dir=args.output,
        feedback_path=feedback,
        novel_review_path=args.novel_review,
    )

    print("MARY DATASET V1")
    print("=" * 64)
    print(f"fingerprint:                   {summary.fingerprint}")
    print(f"sourcebook records:            {summary.sourcebook_records}")
    print(f"character training candidates: {summary.character_training_candidates}")
    print(f"structured behavior SFT:       {summary.behavior_sft}")
    print(f"reviewed novel behavior SFT:   {summary.novel_behavior_sft}")
    print(f"negative examples:             {summary.negative_examples}")
    print(f"held-out MaryBench cases:      {summary.marybench_eval}")
    print(f"explicit feedback records:     {summary.feedback_records}")
    print(f"feedback SFT:                  {summary.feedback_sft}")
    print(f"feedback preferences:          {summary.feedback_preferences}")
    print(f"feedback rejected:             {summary.feedback_rejected}")
    print(f"output:                        {summary.output_dir}")
    print("Policy: no ordinary chat, memory, relationship, growth, profile or trace harvesting.")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
