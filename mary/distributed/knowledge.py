"""Typed locally-owned knowledge capability for MaryV2 nodes."""
from __future__ import annotations

import os
from pathlib import Path
from typing import Any

from mary.distributed.capabilities import CapabilityDescriptor
from mary.knowledge import KnowledgeFabric
from mary.distributed.qdrant_knowledge import (
    EmbeddingSpaceMismatch,
    QdrantKnowledgeBackend,
)


KNOWLEDGE_NODE_CAPABILITIES = frozenset({"knowledge.search", "knowledge.curation"})


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
    all_packs = list(fabric.packs())
    enabled_packs = [pack for pack in all_packs if pack.enabled]
    if not all_packs:
        return []

    descriptors: list[CapabilityDescriptor] = []
    if enabled_packs:
        vector_packs = sum(
            1 for pack in enabled_packs
            if pack.kind in {"qdrant", "qdrant_edge"}
            and pack.query_mode in {"vector", "hybrid"}
        )
        lexical_packs = sum(
            1 for pack in enabled_packs
            if pack.kind == "local_files"
            and pack.query_mode in {"fts", "hybrid"}
        )
        direct_packs = sum(
            1 for pack in enabled_packs
            if pack.kind == "kiwix"
            and pack.query_mode in {"direct", "hybrid"}
        )
        topics = sorted({
            str(topic)
            for pack in enabled_packs
            for topic in list(pack.topics or ())
            if str(topic).strip()
        })[:80]
        descriptors.append(
            CapabilityDescriptor(
                name="knowledge.search",
                available=True,
                private=True,
                local=True,
                cost="local",
                latency="interactive",
                metadata={
                    "execution_authorized": bool(
                        permissions.is_allowed("knowledge.search")
                    ),
                    "implementation_version": str(
                        getattr(fabric, "VERSION", "")
                    )[:80],
                    "ingestion_pipeline_fingerprint": (
                        fabric.local_index_pipeline_fingerprint()
                    ),
                    "packs": len(enabled_packs),
                    "indexed_documents": int(
                        status.get("indexed_documents", 0) or 0
                    ),
                    "lexical_packs": lexical_packs,
                    "direct_packs": direct_packs,
                    "vector_packs": vector_packs,
                    "pack_titles": [
                        str(pack.title)[:120] for pack in enabled_packs[:20]
                    ],
                    "topics": topics,
                    "authority": "retrieval evidence only; not Mary memory/identity",
                    "raw_files_leave_node": False,
                },
            )
        )

    local_packs = [pack for pack in all_packs if pack.kind == "local_files"]
    if local_packs:
        descriptors.append(
            CapabilityDescriptor(
                name="knowledge.curation",
                available=True,
                private=True,
                local=True,
                cost="local",
                latency="interactive",
                metadata={
                    "execution_authorized": bool(
                        permissions.is_allowed("knowledge.curation")
                    ),
                    "implementation_version": str(
                        getattr(fabric, "VERSION", "")
                    )[:80],
                    "ingestion_pipeline_fingerprint": (
                        fabric.local_index_pipeline_fingerprint()
                    ),
                    "local_file_packs": len(local_packs),
                    "enabled_local_file_packs": sum(
                        1 for pack in local_packs if pack.enabled
                    ),
                    "disabled_documents": sum(
                        len(pack.disabled_documents) for pack in local_packs
                    ),
                    "pack_ids": [str(pack.id)[:160] for pack in local_packs[:32]],
                    "pack_titles": [
                        str(pack.title)[:120] for pack in local_packs[:32]
                    ],
                    "authority": (
                        "read-only corpus hygiene evidence only; "
                        "no indexing or source mutation"
                    ),
                    "raw_files_leave_node": False,
                },
            )
        )
    return descriptors


def sanitize_knowledge_task_args(
    capability: str,
    args: dict[str, Any] | None,
) -> dict[str, Any]:
    name = str(capability or "").strip().lower()
    values = dict(args or {})
    if name == "knowledge.curation":
        pack_id = str(values.get("pack_id") or "").strip()[:160]
        return {"pack_id": pack_id}
    if name != "knowledge.search":
        raise ValueError(f"Unsupported knowledge capability: {capability}")

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
    name = str(capability or "").strip().lower()
    values = dict(result or {})
    if name == "knowledge.curation":
        packs: list[dict[str, Any]] = []
        for raw in list(values.get("packs") or [])[:64]:
            if not isinstance(raw, dict):
                continue
            refresh = dict(raw.get("refresh") or {})
            drift = dict(raw.get("drift") or {})
            packs.append({
                "pack_id": str(raw.get("pack_id") or "")[:160],
                "title": str(raw.get("title") or "")[:240],
                "collection": str(raw.get("collection") or "default")[:160],
                "enabled": bool(raw.get("enabled")),
                "documents": max(0, int(raw.get("documents", 0) or 0)),
                "indexed_sources": max(
                    0, int(raw.get("indexed_sources", 0) or 0)
                ),
                "disabled_documents": max(
                    0, int(raw.get("disabled_documents", 0) or 0)
                ),
                "refresh": {
                    "added": max(0, int(refresh.get("added", 0) or 0)),
                    "changed": max(0, int(refresh.get("changed", 0) or 0)),
                    "removed": max(0, int(refresh.get("removed", 0) or 0)),
                    "skipped": max(0, int(refresh.get("skipped", 0) or 0)),
                    "has_changes": bool(refresh.get("has_changes")),
                },
                "drift": {
                    key: [
                        str(item)[:500]
                        for item in list(drift.get(key) or [])[:200]
                        if str(item).strip()
                    ]
                    for key in (
                        "manifest_only",
                        "index_only",
                        "disabled_missing",
                    )
                },
                "recommendations": [
                    str(item)[:120]
                    for item in list(raw.get("recommendations") or [])[:16]
                    if str(item).strip()
                ],
            })
        duplicate_groups: list[dict[str, Any]] = []
        for raw in list(values.get("duplicate_content_groups") or [])[:200]:
            if not isinstance(raw, dict):
                continue
            copies = []
            for item in list(raw.get("copies") or [])[:50]:
                if not isinstance(item, dict):
                    continue
                copies.append({
                    "pack_id": str(item.get("pack_id") or "")[:160],
                    "locator": str(item.get("locator") or "")[:500],
                })
            if len(copies) > 1:
                duplicate_groups.append({
                    "content_hash": str(raw.get("content_hash") or "")[:128],
                    "copies": copies,
                })
        return {
            "ok": bool(values.get("ok", True)),
            "version": max(0, int(values.get("version", 1) or 1)),
            "pack_id": str(values.get("pack_id") or "")[:160],
            "packs": packs,
            "duplicate_content_groups": duplicate_groups,
            "duplicate_content_group_count": len(duplicate_groups),
            "automatic_mutation_performed": False,
            "recommended_policy": str(
                values.get("recommended_policy") or ""
            )[:500],
            "authority": "node-local read-only corpus curation evidence",
            "raw_files_leave_node": False,
        }

    if name != "knowledge.search":
        return {}

    hits: list[dict[str, Any]] = []
    for raw in list(values.get("hits") or [])[:20]:
        if not isinstance(raw, dict):
            continue
        hits.append({
            "pack_id": str(raw.get("pack_id") or "")[:160],
            "title": str(raw.get("title") or "")[:240],
            "snippet": str(raw.get("snippet") or "")[:1200],
            "source": str(raw.get("source") or "")[:300],
            "score": max(
                0.0, min(1000.0, float(raw.get("score", 0.0) or 0.0))
            ),
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
        "vector_errors": [
            {
                "pack_id": str(item.get("pack_id") or "")[:160],
                "error_class": str(item.get("error_class") or "")[:80],
            }
            for item in list(values.get("vector_errors") or [])[:20]
            if isinstance(item, dict)
        ],
        "authority": "node-local knowledge evidence only",
    }


def execute_knowledge_curation(args: dict[str, Any]) -> dict[str, Any]:
    """Return sanitized, read-only corpus hygiene evidence from this node."""

    values = sanitize_knowledge_task_args("knowledge.curation", args)
    report = node_knowledge_fabric().curation_report(values["pack_id"])
    return sanitize_knowledge_result(
        "knowledge.curation",
        {"ok": True, **report},
    )


def execute_knowledge_search(
    args: dict[str, Any],
    *,
    qdrant_backend: QdrantKnowledgeBackend | None = None,
) -> dict[str, Any]:
    values = sanitize_knowledge_task_args("knowledge.search", args)
    fabric = node_knowledge_fabric()
    mode = values["retrieval_mode"]
    hits = fabric.search(
        values["query"],
        pack_ids=values["pack_ids"],
        limit=values["limit"],
        retrieval_mode=mode,
    )

    selected = set(values["pack_ids"])
    packs = [
        pack for pack in fabric.packs(enabled_only=True)
        if not selected or pack.id in selected
    ]
    vector_packs = [
        pack for pack in packs
        if pack.kind in {"qdrant", "qdrant_edge"}
        and pack.query_mode in {"vector", "hybrid"}
        and mode in {"auto", "vector", "hybrid"}
    ]
    vector_errors: list[dict[str, str]] = []
    backend = qdrant_backend
    if vector_packs and backend is None:
        backend = QdrantKnowledgeBackend()

    for pack in vector_packs:
        try:
            assert backend is not None
            hits.extend(
                backend.search(
                    pack,
                    values["query"],
                    limit=values["limit"],
                )
            )
        except EmbeddingSpaceMismatch:
            vector_errors.append({
                "pack_id": pack.id,
                "error_class": "embedding_space_mismatch",
            })
        except Exception as exc:
            vector_errors.append({
                "pack_id": pack.id,
                "error_class": type(exc).__name__[:80],
            })

    deduplicated = {}
    for item in sorted(hits, key=lambda row: row.score, reverse=True):
        key = item.citation_id or item.content_hash or (
            f"{item.pack_id}:{item.locator}:{item.title}"
        )
        deduplicated.setdefault(key, item)
    bounded = list(deduplicated.values())[: values["limit"]]

    vector_only_failure = bool(
        mode == "vector"
        and vector_packs
        and not bounded
        and len(vector_errors) == len(vector_packs)
    )
    return {
        "ok": not vector_only_failure,
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
            for item in bounded
        ],
        "pack_count": len(packs),
        "retrieval_mode": mode,
        "vector_errors": vector_errors,
    }
