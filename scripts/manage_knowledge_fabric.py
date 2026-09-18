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
from mary.mind.embeddings import OllamaEmbeddingClient


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
    register.add_argument("--collection", default="default")
    register.add_argument("--license", default="creator-owned")

    kiwix = sub.add_parser("register-kiwix")
    kiwix.add_argument("pack_id")
    kiwix.add_argument("title")
    kiwix.add_argument("endpoint")
    kiwix.add_argument("--book", default="")
    kiwix.add_argument("--topics", default="")
    kiwix.add_argument("--collection", default="default")
    kiwix.add_argument("--license", default="content-specific")

    qdrant = sub.add_parser("register-qdrant")
    qdrant.add_argument("pack_id")
    qdrant.add_argument("title")
    qdrant.add_argument("endpoint")
    qdrant.add_argument("--qdrant-collection", required=True)
    qdrant.add_argument("--embedding-model", required=True)
    qdrant.add_argument("--embedding-space-identity", required=True)
    qdrant.add_argument("--embedding-dimensions", type=int, required=True)
    qdrant.add_argument("--vector-name", default="")
    qdrant.add_argument("--topics", default="")
    qdrant.add_argument("--collection", default="default")
    qdrant.add_argument("--license", default="creator-owned-derived-index")
    qdrant.add_argument(
        "--hybrid",
        action="store_true",
        help="mark the pack as hybrid instead of vector-only",
    )

    embedding_identity = sub.add_parser("embedding-identity")
    embedding_identity.add_argument("--model", default="")

    index = sub.add_parser("index")
    index.add_argument("pack_id")

    search = sub.add_parser("search")
    search.add_argument("query")
    search.add_argument("--pack", action="append", default=[])
    search.add_argument(
        "--mode",
        choices=sorted(KnowledgeFabric.RETRIEVAL_MODES),
        default="auto",
    )
    search.add_argument("--limit", type=int, default=8)

    documents = sub.add_parser("documents")
    documents.add_argument("pack_id")
    document_enable = sub.add_parser("document-enable")
    document_enable.add_argument("pack_id")
    document_enable.add_argument("locator")
    document_disable = sub.add_parser("document-disable")
    document_disable.add_argument("pack_id")
    document_disable.add_argument("locator")
    collection_enable = sub.add_parser("collection-enable")
    collection_enable.add_argument("collection")
    collection_disable = sub.add_parser("collection-disable")
    collection_disable.add_argument("collection")

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
            collection=args.collection,
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
            collection=args.collection,
            license=args.license,
            local_only=True,
            source="creator_cli",
            metadata={"book": args.book} if args.book else {},
        )
        print(json.dumps(pack.to_dict(), indent=2, ensure_ascii=False))
        return 0

    if args.command == "register-qdrant":
        topics = [item.strip() for item in args.topics.split(",") if item.strip()]
        pack = fabric.register(
            pack_id=args.pack_id,
            title=args.title,
            kind="qdrant",
            location=args.endpoint,
            query_mode="hybrid" if args.hybrid else "vector",
            topics=topics,
            collection=args.collection,
            license=args.license,
            local_only=True,
            source="creator_cli",
            metadata={
                "qdrant_collection": args.qdrant_collection,
                "embedding_model": args.embedding_model,
                "embedding_space_identity": args.embedding_space_identity,
                "embedding_dimensions": args.embedding_dimensions,
                **({"vector_name": args.vector_name} if args.vector_name else {}),
            },
        )
        print(json.dumps(pack.to_dict(), indent=2, ensure_ascii=False))
        return 0

    if args.command == "embedding-identity":
        client = OllamaEmbeddingClient(
            model=(args.model or None),
            timeout=15.0,
        )
        identity = client.embedding_identity(refresh=True)
        vector = client.embed("MaryV2 embedding-space identity probe")
        print(json.dumps({
            "identity": identity.to_dict(),
            "dimensions": len(vector),
            "model_available": client.model_available(),
            "authority": "local embedding configuration evidence only",
        }, indent=2, ensure_ascii=False))
        return 0 if vector else 2

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
            retrieval_mode=args.mode,
        )
        print(json.dumps(
            [item.to_dict() for item in hits],
            indent=2,
            ensure_ascii=False,
        ))
        return 0

    if args.command == "documents":
        print(json.dumps(fabric.documents(args.pack_id), indent=2, ensure_ascii=False))
        return 0

    if args.command == "document-enable":
        print(json.dumps(
            fabric.enable_document(args.pack_id, args.locator),
            indent=2,
            ensure_ascii=False,
        ))
        return 0

    if args.command == "document-disable":
        print(json.dumps(
            fabric.disable_document(args.pack_id, args.locator),
            indent=2,
            ensure_ascii=False,
        ))
        return 0

    if args.command == "collection-enable":
        print(json.dumps(
            [item.to_dict() for item in fabric.enable_collection(args.collection)],
            indent=2,
            ensure_ascii=False,
        ))
        return 0

    if args.command == "collection-disable":
        print(json.dumps(
            [item.to_dict() for item in fabric.disable_collection(args.collection)],
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
