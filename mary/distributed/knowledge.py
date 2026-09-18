"""Typed locally-owned knowledge capability for MaryV2 nodes."""
from __future__ import annotations

import os
from pathlib import Path
from typing import Any

from mary.distributed.capabilities import CapabilityDescriptor
from mary.knowledge import KnowledgeFabric


KNOWLEDGE_NODE_CAPABILITIES = frozenset({"knowledge.search"})


def node_knowledge_paths() -> tuple[Path, Path]:
    configured = os.getenv("MARY_KNOWLEDGE_NODE_ROOT", "").strip()
    root = (
        Path(configured).expanduser().resolve()
        if configured
        else Path.home() / ".maryv2" / "knowledge-node"
    )
    return root / "knowledge_fabric.json", root / "knowledge_fabric.sqlite3"


def node_knowledge_fabric() -> KnowledgeFabric:
    registry, index = node_knowledge_paths()
    return KnowledgeFabric(registry, index_path=index)


def knowledge_capability_descriptors(permissions: Any) -> list[CapabilityDescriptor]:
    fabric = node_knowledge_fabric()
    status = dict(fabric.status() or {})
    packs = list(fabric.packs(enabled_only=True))
    if not packs:
        return []
    topics = sorted({
        str(topic)
        for pack in packs
        for topic in list(pack.topics or ())
        if str(topic).strip()
    })[:80]
    return [
        CapabilityDescriptor(
            name="knowledge.search",
            available=True,
            private=True,
            local=True,
            cost="local",
            latency="interactive",
            metadata={
                "execution_authorized": bool(permissions.is_allowed("knowledge.search")),
                "packs": len(packs),
                "indexed_documents": int(status.get("indexed_documents", 0) or 0),
                "pack_titles": [str(pack.title)[:120] for pack in packs[:20]],
                "topics": topics,
                "authority": "retrieval evidence only; not Mary memory/identity",
                "raw_files_leave_node": False,
            },
        )
    ]


def sanitize_knowledge_task_args(
    capability: str,
    args: dict[str, Any] | None,
) -> dict[str, Any]:
    if str(capability or "").strip().lower() != "knowledge.search":
        raise ValueError(f"Unsupported knowledge capability: {capability}")
    values = dict(args or {})
    query = " ".join(str(values.get("query") or "").split())[:500]
    if not query:
        raise ValueError("knowledge.search requires a query")
    limit = max(1, min(20, int(values.get("limit", 8) or 8)))
    retrieval_mode = str(values.get("retrieval_mode") or "auto").strip().lower()
    if retrieval_mode not in KnowledgeFabric.RETRIEVAL_MODES:
        raise ValueError(
            "knowledge.search retrieval_mode must be one of "
            + ", ".join(sorted(KnowledgeFabric.RETRIEVAL_MODES))
        )
    raw_pack_ids = values.get("pack_ids") or []
    if not isinstance(raw_pack_ids, (list, tuple)):
        raise ValueError("knowledge.search pack_ids must be a list")
    pack_ids = list(dict.fromkeys(
        str(item or "").strip()[:160]
        for item in list(raw_pack_ids)[:32]
        if str(item or "").strip()
    ))
    return {
        "query": query,
        "limit": limit,
        "retrieval_mode": retrieval_mode,
        "pack_ids": pack_ids,
    }


def sanitize_knowledge_result(
    capability: str,
    result: dict[str, Any] | None,
) -> dict[str, Any]:
    if str(capability or "").strip().lower() != "knowledge.search":
        return {}
    values = dict(result or {})
    hits: list[dict[str, Any]] = []
    for raw in list(values.get("hits") or [])[:20]:
        if not isinstance(raw, dict):
            continue
        hits.append({
            "pack_id": str(raw.get("pack_id") or "")[:160],
            "title": str(raw.get("title") or "")[:240],
            "snippet": str(raw.get("snippet") or "")[:1200],
            "source": str(raw.get("source") or "")[:300],
            "score": max(0.0, min(1000.0, float(raw.get("score", 0.0) or 0.0))),
            "locator": str(raw.get("locator") or "")[:500],
            "content_hash": str(raw.get("content_hash") or "")[:128],
            "collection": str(raw.get("collection") or "default")[:160],
            "source_date": str(raw.get("source_date") or "")[:80],
            "indexed_at": str(raw.get("indexed_at") or "")[:80],
            "citation_id": str(raw.get("citation_id") or "")[:220],
        })
    return {
        "ok": bool(values.get("ok", True)),
        "hits": hits,
        "pack_count": max(0, int(values.get("pack_count", 0) or 0)),
        "retrieval_mode": str(values.get("retrieval_mode") or "auto")[:40],
        "authority": "node-local knowledge evidence only",
    }


def execute_knowledge_search(args: dict[str, Any]) -> dict[str, Any]:
    values = sanitize_knowledge_task_args("knowledge.search", args)
    fabric = node_knowledge_fabric()
    hits = fabric.search(
        values["query"],
        pack_ids=values["pack_ids"],
        limit=values["limit"],
        retrieval_mode=values["retrieval_mode"],
    )
    return {
        "ok": True,
        "hits": [
            {
                "pack_id": item.pack_id,
                "title": item.title,
                "snippet": item.snippet,
                "source": item.source,
                "score": item.score,
                "locator": item.locator,
                "content_hash": item.content_hash,
                "collection": item.collection,
                "source_date": item.source_date,
                "indexed_at": item.indexed_at,
                "citation_id": item.citation_id,
            }
            for item in hits
        ],
        "pack_count": len(fabric.packs(enabled_only=True)),
        "retrieval_mode": values["retrieval_mode"],
    }
