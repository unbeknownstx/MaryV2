"""Manage one node-local Mary knowledge fabric explicitly.

Nothing is downloaded or enabled automatically. This command only registers
creator-chosen local folders/endpoints, rebuilds disposable indexes, and performs
read-only searches.
"""
from __future__ import annotations

import argparse
import json
from pathlib import Path

from mary.distributed.knowledge import node_knowledge_fabric
from mary.knowledge import KnowledgeFabric


def _fabric(root: Path | None) -> KnowledgeFabric:
    if root is None:
        return node_knowledge_fabric()
    resolved = root.expanduser().resolve()
    return KnowledgeFabric(
        resolved / "knowledge_fabric.json",
        index_path=resolved / "knowledge_fabric.sqlite3",
    )


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument(
        "--root",
        type=Path,
        default=None,
        help="Override the node-local knowledge root.",
    )
    sub = parser.add_subparsers(dest="command", required=True)

    sub.add_parser("status")
    sub.add_parser("list")
    sub.add_parser("seed-candidates")

    register = sub.add_parser("register-files")
    register.add_argument("pack_id")
    register.add_argument("title")
    register.add_argument("directory", type=Path)
    register.add_argument("--topics", default="")
    register.add_argument("--license", default="creator-owned")

    kiwix = sub.add_parser("register-kiwix")
    kiwix.add_argument("pack_id")
    kiwix.add_argument("title")
    kiwix.add_argument("endpoint")
    kiwix.add_argument("--book", default="")
    kiwix.add_argument("--topics", default="")
    kiwix.add_argument("--license", default="content-specific")

    index = sub.add_parser("index")
    index.add_argument("pack_id")

    search = sub.add_parser("search")
    search.add_argument("query")
    search.add_argument("--pack", action="append", default=[])
    search.add_argument("--limit", type=int, default=8)

    enable = sub.add_parser("enable")
    enable.add_argument("pack_id")
    disable = sub.add_parser("disable")
    disable.add_argument("pack_id")

    args = parser.parse_args()
    fabric = _fabric(args.root)

    if args.command == "status":
        print(json.dumps(fabric.status(), indent=2, ensure_ascii=False))
        return 0

    if args.command == "list":
        print(json.dumps(
            [pack.to_dict() for pack in fabric.packs()],
            indent=2,
            ensure_ascii=False,
        ))
        return 0

    if args.command == "seed-candidates":
        rows = fabric.seed_recommended_candidates()
        print(json.dumps([item.to_dict() for item in rows], indent=2, ensure_ascii=False))
        return 0

    if args.command == "register-files":
        topics = [item.strip() for item in args.topics.split(",") if item.strip()]
        pack = fabric.register(
            pack_id=args.pack_id,
            title=args.title,
            kind="local_files",
            location=str(args.directory),
            query_mode="fts",
            topics=topics,
            license=args.license,
            local_only=True,
            source="creator_cli",
        )
        print(json.dumps(pack.to_dict(), indent=2, ensure_ascii=False))
        return 0

    if args.command == "register-kiwix":
        topics = [item.strip() for item in args.topics.split(",") if item.strip()]
        pack = fabric.register(
            pack_id=args.pack_id,
            title=args.title,
            kind="kiwix",
            location=args.endpoint,
            query_mode="direct",
            topics=topics,
            license=args.license,
            local_only=True,
            source="creator_cli",
            metadata={"book": args.book} if args.book else {},
        )
        print(json.dumps(pack.to_dict(), indent=2, ensure_ascii=False))
        return 0

    if args.command == "index":
        print(json.dumps(
            fabric.index_local_pack(args.pack_id),
            indent=2,
            ensure_ascii=False,
        ))
        return 0

    if args.command == "search":
        hits = fabric.search(
            args.query,
            pack_ids=args.pack,
            limit=max(1, min(50, int(args.limit))),
        )
        print(json.dumps(
            [item.to_dict() for item in hits],
            indent=2,
            ensure_ascii=False,
        ))
        return 0

    if args.command == "enable":
        print(json.dumps(fabric.enable(args.pack_id).to_dict(), indent=2))
        return 0

    if args.command == "disable":
        print(json.dumps(fabric.disable(args.pack_id).to_dict(), indent=2))
        return 0

    raise SystemExit("unsupported command")


if __name__ == "__main__":
    raise SystemExit(main())
