"""Create a review-only Mary model-candidate proposal from a trained MLX adapter."""
from __future__ import annotations

import argparse
import json
from pathlib import Path

from mary.training import build_mlx_adapter_candidate_proposal


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--bundle", type=Path, required=True)
    parser.add_argument("--candidate-id", default="")
    parser.add_argument("--output", type=Path, default=None)
    args = parser.parse_args()

    proposal = build_mlx_adapter_candidate_proposal(
        args.bundle,
        candidate_id=args.candidate_id,
    ).to_dict()
    rendered = json.dumps(proposal, indent=2, ensure_ascii=False)
    if args.output is not None:
        args.output.parent.mkdir(parents=True, exist_ok=True)
        args.output.write_text(rendered + "\n", encoding="utf-8")
    print(rendered)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
