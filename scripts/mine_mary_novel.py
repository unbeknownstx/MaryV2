"""Extract review-only Mary scene candidates from a local manuscript."""
from __future__ import annotations

import argparse
from pathlib import Path

from mary.training import mine_mary_scenes, write_mining_bundle


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("manuscript", type=Path, help="Local .docx/.txt/.md manuscript path")
    parser.add_argument(
        "--output",
        type=Path,
        default=Path.home() / ".maryv2" / "datasets" / "mary-novel-mining-v1.json",
    )
    parser.add_argument("--character", default="Mary")
    parser.add_argument("--context-paragraphs", type=int, default=3)
    parser.add_argument("--max-characters", type=int, default=5000)
    args = parser.parse_args()

    payload = mine_mary_scenes(
        args.manuscript,
        character_name=args.character,
        context_paragraphs=args.context_paragraphs,
        max_characters=args.max_characters,
    )
    target = write_mining_bundle(payload, args.output)

    print("MARY NOVEL MINING V1")
    print("=" * 64)
    print(f"source:      {payload['source']['file']}")
    print(f"sha256:      {payload['source']['sha256']}")
    print(f"paragraphs:  {payload['source']['paragraphs']}")
    print(f"candidates:  {len(payload['candidates'])}")
    print(f"output:      {target}")
    print("Boundary: fictional reference only; every candidate requires creator review.")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
