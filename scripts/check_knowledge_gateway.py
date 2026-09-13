"""Inspect or explicitly live-probe Mary's optional public knowledge gateway."""
from __future__ import annotations

import argparse
import json

from mary.knowledge.gateway import KnowledgeGateway


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("query", nargs="?", default="artificial intelligence")
    parser.add_argument("--live", action="store_true", help="perform explicit external HTTP lookups")
    parser.add_argument("--category", action="append", default=[])
    parser.add_argument("--limit", type=int, default=2)
    args = parser.parse_args()

    gateway = KnowledgeGateway()
    print(json.dumps(gateway.status(), indent=2, sort_keys=True))
    if not args.live:
        print("Live lookup not requested. Re-run with --live to contact configured/public knowledge sources.")
        return 0

    results = gateway.search(
        args.query,
        categories=args.category or None,
        limit_per_source=max(1, min(5, args.limit)),
    )
    print(json.dumps({"query": args.query, "result_count": len(results), "results": results}, indent=2, ensure_ascii=False))
    return 0 if results else 2


if __name__ == "__main__":
    raise SystemExit(main())
