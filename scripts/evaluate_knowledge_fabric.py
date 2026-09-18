"""Run deterministic regression cases against a local Mary KnowledgeFabric."""
from __future__ import annotations

import argparse
import json
from pathlib import Path

from mary.knowledge import (
    KnowledgeFabric,
    KnowledgeFabricEvaluator,
    load_knowledge_evaluation_cases,
)


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--registry", type=Path, required=True)
    parser.add_argument("--index", type=Path, required=True)
    parser.add_argument("--cases", type=Path, required=True)
    parser.add_argument("--output", type=Path, default=None)
    args = parser.parse_args()

    fabric = KnowledgeFabric(args.registry, index_path=args.index)
    summary = KnowledgeFabricEvaluator(fabric).evaluate(
        load_knowledge_evaluation_cases(args.cases)
    )
    if args.output is not None:
        args.output.parent.mkdir(parents=True, exist_ok=True)
        args.output.write_text(
            json.dumps(summary, indent=2, ensure_ascii=False),
            encoding="utf-8",
        )
    print(json.dumps(summary, indent=2, ensure_ascii=False))
    return 0 if summary["all_passed"] else 2


if __name__ == "__main__":
    raise SystemExit(main())
