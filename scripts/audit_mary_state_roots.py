"""Compare Mary state roots without mutating either one.

Example:
  python -m scripts.audit_mary_state_roots local=C:\\MaryData cloud=C:\\CloudSnapshot --out reconciliation.json
"""
from __future__ import annotations
import argparse, json
from pathlib import Path
from mary.runtime.state_reconciliation import StateReconciler


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("roots", nargs="+", help="name=path pairs")
    parser.add_argument("--out", default="mary_state_reconciliation.json")
    args = parser.parse_args()
    roots = {}
    for value in args.roots:
        if "=" not in value:
            parser.error(f"expected name=path, got {value!r}")
        name, path = value.split("=", 1)
        roots[name.strip()] = path.strip()
    plan = StateReconciler.plan(roots)
    Path(args.out).write_text(json.dumps(plan, indent=2, ensure_ascii=False), encoding="utf-8")
    print(f"Mary state reconciliation: {args.out}")
    print(json.dumps({
        "comparison_ready": plan["comparison_ready"],
        "inventory_counts": plan["inventory_counts"],
        "classifications": plan["classifications"],
    }, indent=2))
    if not plan["comparison_ready"]:
        print("INVENTORY ONLY: add a second independent root before interpreting comparison classes.")
    print("READ ONLY: no Mary state was modified.")
    return 0

if __name__ == "__main__":
    raise SystemExit(main())
