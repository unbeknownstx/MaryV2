"""Prepare a reviewed Mary Dataset v1 bundle for local MLX LoRA/QLoRA."""
from __future__ import annotations

import argparse
import json
from pathlib import Path

from mary.core.config import Config
from mary.training.mlx_bundle import PROFILES, prepare_mlx_bundle


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--root", type=Path, default=Path.cwd())
    parser.add_argument(
        "--output",
        type=Path,
        default=Path.home() / ".maryv2" / "training" / "mary-mlx-adapter-v1",
    )
    parser.add_argument("--profile", choices=sorted(PROFILES), default="m1-light")
    parser.add_argument("--feedback", type=Path, default=None)
    parser.add_argument(
        "--novel-review",
        type=Path,
        default=None,
        help="Optional creator-approved novel behavior abstraction review JSON.",
    )
    args = parser.parse_args()

    feedback = args.feedback
    if feedback is None:
        candidate = Path(Config.from_environment().paths.data) / "training" / "response_feedback.json"
        feedback = candidate if candidate.exists() else None

    manifest = prepare_mlx_bundle(
        root=args.root,
        output_dir=args.output,
        profile_id=args.profile,
        feedback_path=feedback,
        novel_review_path=args.novel_review,
    )
    print("MARY MLX ADAPTER BUNDLE")
    print("=" * 64)
    print(f"profile:    {manifest['profile']['profile_id']}")
    print(f"model:      {manifest['profile']['model']}")
    print(f"dataset:    {manifest['mary_dataset']['fingerprint']}")
    print(f"train:      {manifest['examples']['train']}")
    print(f"validation: {manifest['examples']['validation']}")
    print(f"test:       {manifest['examples']['test']}")
    print(f"output:     {args.output.expanduser().resolve()}")
    print("No training was performed. Review manifest.json and config before running MLX-LM.")
    print(json.dumps(manifest["run"], indent=2))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
