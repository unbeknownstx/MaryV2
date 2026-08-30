"""Create an explicit secret-free Mary recovery manifest/snapshot."""
from __future__ import annotations
import argparse, json
from mary.runtime.recovery import MaryRecovery


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("roots", nargs="+", help="name=path pairs, e.g. repo=. state=data")
    parser.add_argument("--destination", required=True)
    parser.add_argument("--copy", action="store_true", help="actually copy safe files; default writes manifest only")
    args = parser.parse_args()
    roots = {}
    for value in args.roots:
        if "=" not in value:
            parser.error(f"expected name=path, got {value!r}")
        name, path = value.split("=", 1)
        roots[name.strip()] = path.strip()
    result = MaryRecovery.create_snapshot(roots, args.destination, copy_files=args.copy)
    print(json.dumps(result, indent=2))
    return 0

if __name__ == "__main__":
    raise SystemExit(main())
