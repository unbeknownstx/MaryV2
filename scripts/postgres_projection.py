"""Manage Mary's optional PostgreSQL/pgvector projection.

Examples:
    python -m scripts.postgres_projection status
    python -m scripts.postgres_projection init
    python -m scripts.postgres_projection sync
    python -m scripts.postgres_projection search "streaming plans"
    python -m scripts.postgres_projection embed --limit 500

The database is never a startup dependency and never becomes canonical state.
"""

from __future__ import annotations

import argparse
import json
from typing import Any

from mary.storage.postgres_projection import PostgresProjection


def _print(value: Any) -> None:
    print(json.dumps(value, indent=2, ensure_ascii=False, default=str))


def _projection() -> PostgresProjection:
    return PostgresProjection()


def _cmd_status(_args: argparse.Namespace) -> int:
    _print(_projection().status())
    return 0


def _cmd_init(_args: argparse.Namespace) -> int:
    result = _projection().ensure_schema()
    _print(result)
    return 0 if result.get("ok") else 1


def _cmd_sync(_args: argparse.Namespace) -> int:
    from mary.runtime.application import create_application

    projection = _projection()
    app = create_application(name="postgres-projection-sync")
    try:
        result = projection.sync_memory(app.mary.memory)
    finally:
        try:
            app.close()
        except Exception:
            pass
    _print(result)
    return 0 if result.get("ok") else 1


def _cmd_search(args: argparse.Namespace) -> int:
    projection = _projection()
    results = projection.lexical_search(args.query, limit=args.limit)
    _print({"query": args.query, "results": results})
    return 0


def _embedding_identity(client: Any) -> tuple[str, dict[str, Any]]:
    resolver = getattr(client, "embedding_identity", None)
    if callable(resolver):
        try:
            identity = resolver(refresh=True)
        except TypeError:
            identity = resolver()
        if isinstance(identity, dict):
            fingerprint = str(identity.get("fingerprint") or "").strip()
            return fingerprint, dict(identity)
        fingerprint = getattr(identity, "fingerprint", "")
        if callable(fingerprint):
            fingerprint = fingerprint()
        to_dict = getattr(identity, "to_dict", None)
        details = dict(to_dict()) if callable(to_dict) else {"value": str(identity)}
        return str(fingerprint or "").strip(), details
    model = str(getattr(client, "model", "unknown"))
    return f"legacy:{model}", {"provider": "legacy", "model": model}


def _cmd_embed(args: argparse.Namespace) -> int:
    from mary.mind.embeddings import OllamaEmbeddingClient

    projection = _projection()
    schema = projection.ensure_schema()
    if not schema.get("ok"):
        _print(schema)
        return 1
    if not schema.get("vector"):
        _print({
            "ok": False,
            "reason": "pgvector extension is unavailable on this database",
        })
        return 1

    client = OllamaEmbeddingClient(timeout=float(args.timeout))
    if not client.model_available():
        _print({
            "ok": False,
            "reason": "configured Ollama embedding model is unavailable",
            "model": client.model,
        })
        return 1

    identity, identity_details = _embedding_identity(client)
    records = projection.list_records(limit=args.limit)
    indexed = 0
    errors = 0
    for record in records:
        try:
            vector = client.embed(str(record.get("content") or ""))
            if vector and projection.upsert_vector(
                record_id=str(record["record_id"]),
                vector=vector,
                model=client.model,
                embedding_identity=identity,
                content_hash=str(record["content_hash"]),
            ):
                indexed += 1
            else:
                errors += 1
        except Exception:
            errors += 1

    result = {
        "ok": errors == 0 or indexed > 0,
        "requested": len(records),
        "indexed": indexed,
        "errors": errors,
        "model": client.model,
        "embedding_identity": identity,
        "embedding_identity_details": identity_details,
        "authority": "derived_projection_only",
    }
    _print(result)
    return 0 if result["ok"] else 1


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        description="MaryV2 optional PostgreSQL/pgvector projection manager"
    )
    sub = parser.add_subparsers(dest="command", required=True)

    status = sub.add_parser("status", help="Show safe local configuration only")
    status.set_defaults(handler=_cmd_status)

    init = sub.add_parser("init", help="Create projection schema and pgvector tables")
    init.set_defaults(handler=_cmd_init)

    sync = sub.add_parser("sync", help="Project current canonical durable memory")
    sync.set_defaults(handler=_cmd_sync)

    search = sub.add_parser("search", help="Query the PostgreSQL full-text projection")
    search.add_argument("query")
    search.add_argument("--limit", type=int, default=8)
    search.set_defaults(handler=_cmd_search)

    embed = sub.add_parser(
        "embed",
        help="Build pgvector rows using the existing local Ollama embedding model",
    )
    embed.add_argument("--limit", type=int, default=1000)
    embed.add_argument("--timeout", type=float, default=10.0)
    embed.set_defaults(handler=_cmd_embed)
    return parser


def main() -> int:
    args = build_parser().parse_args()
    return int(args.handler(args))


if __name__ == "__main__":
    raise SystemExit(main())
