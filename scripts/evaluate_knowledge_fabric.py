"""Run deterministic regression cases against a local Mary KnowledgeFabric."""
from __future__ import annotations

import argparse
import json
from pathlib import Path

from mary.knowledge import (
    KnowledgeFabric,
    KnowledgeFabricEvaluator,
    KnowledgeEvaluationEvidenceStore,
    knowledge_substrate_fingerprint,
    knowledge_case_set_fingerprint,
    load_knowledge_evaluation_cases,
)


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--registry", type=Path, required=True)
    parser.add_argument("--index", type=Path, required=True)
    parser.add_argument("--cases", type=Path, required=True)
    parser.add_argument("--output", type=Path, default=None)
    parser.add_argument(
        "--evidence",
        type=Path,
        default=None,
        help="Optional content-free durable evaluation evidence file.",
    )
    args = parser.parse_args()

    fabric = KnowledgeFabric(args.registry, index_path=args.index)
    cases = load_knowledge_evaluation_cases(args.cases)
    summary = KnowledgeFabricEvaluator(fabric).evaluate(cases)
    if args.output is not None:
        args.output.parent.mkdir(parents=True, exist_ok=True)
        args.output.write_text(
            json.dumps(summary, indent=2, ensure_ascii=False),
            encoding="utf-8",
        )
    if args.evidence is not None:
        KnowledgeEvaluationEvidenceStore(args.evidence).record(
            summary,
            substrate_fingerprint=knowledge_substrate_fingerprint(fabric),
            case_set_fingerprint=knowledge_case_set_fingerprint(cases),
        )
    print(json.dumps(summary, indent=2, ensure_ascii=False))
    return 0 if summary["all_passed"] else 2


if __name__ == "__main__":
    raise SystemExit(main())
