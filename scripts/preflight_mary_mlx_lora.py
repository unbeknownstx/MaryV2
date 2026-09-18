"""Check a Mary MLX adapter bundle before any explicit training/evaluation."""
from __future__ import annotations

import argparse
import json
from pathlib import Path

from mary.training.mlx_preflight import inspect_mlx_bundle


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--bundle", type=Path, required=True)
    args = parser.parse_args()

    report = inspect_mlx_bundle(args.bundle)
    print("MARY MLX PREFLIGHT")
    print("=" * 64)
    print(json.dumps(report.to_dict(), indent=2, ensure_ascii=False))
    return 0 if report.ready_for_training else 2


if __name__ == "__main__":
    raise SystemExit(main())
