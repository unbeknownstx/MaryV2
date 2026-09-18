"""Optional node-local Qdrant semantic retrieval for MaryV2 knowledge packs.

Qdrant is a rebuildable derived index, never Mary memory or truth authority.
The adapter is deliberately read-only and local/private only.  Every query
verifies the exact embedding-space fingerprint and dimensions recorded by the
pack before comparing vectors.
"""
from __future__ import annotations

from hashlib import sha256
import json
import re
from typing import Any, Callable
from urllib.parse import quote
from urllib.request import Request, urlopen

from mary.knowledge import KnowledgeFabric, KnowledgeHit, KnowledgePack
from mary.mind.embeddings import OllamaEmbeddingClient


_COLLECTION_RE = re.compile(r"^[A-Za-z0-9_.-]{1,200}$")


class EmbeddingSpaceMismatch(RuntimeError):
    """Raised when a derived vector index cannot be queried safely."""


class QdrantKnowledgeBackend:
    VERSION = 1

    def __init__(
        self,
        *,
        embedding_client_factory: Callable[[str], Any] | None = None,
        request_json: Callable[[str, dict[str, Any]], dict[str, Any]] | None = None,
        timeout: float = 5.0,
    ) -> None:
        self.embedding_client_factory = (
            embedding_client_factory
            or (lambda model: OllamaEmbeddingClient(model=model, timeout=timeout))
        )
        self.request_json = request_json or self._request_json
        self.timeout = max(0.5, min(30.0, float(timeout)))

    def _request_json(
        self,
        url: str,
        payload: dict[str, Any],
    ) -> dict[str, Any]:
        request = Request(
            url,
            data=json.dumps(payload).encode("utf-8"),
            headers={
                "Accept": "application/json",
                "Content-Type": "application/json",
                "User-Agent": "MaryV2-QdrantKnowledge/1",
            },
            method="POST",
        )
        with urlopen(request, timeout=self.timeout) as response:  # nosec B310 - endpoint is validated local/private
            raw = response.read(4 * 1024 * 1024)
        decoded = json.loads(raw.decode("utf-8"))
        return dict(decoded) if isinstance(decoded, dict) else {}

    @staticmethod
    def _fingerprint(identity: Any) -> str:
        if isinstance(identity, dict):
            return str(identity.get("fingerprint") or "").strip()
        value = getattr(identity, "fingerprint", "")
        if callable(value):
            value = value()
        return str(value or "").strip()

    @staticmethod
    def _metadata(pack: KnowledgePack) -> tuple[str, str, int, str]:
        metadata = dict(pack.metadata or {})
        collection = str(metadata.get("qdrant_collection") or "").strip()
        embedding_model = str(metadata.get("embedding_model") or "").strip()
        expected_identity = str(
            metadata.get("embedding_space_identity") or ""
        ).strip()
        try:
            dimensions = int(metadata.get("embedding_dimensions") or 0)
        except (TypeError, ValueError):
            dimensions = 0
        vector_name = str(metadata.get("vector_name") or "").strip()

        if not _COLLECTION_RE.fullmatch(collection):
            raise ValueError("Qdrant pack requires a safe qdrant_collection")
        if not embedding_model:
            raise ValueError("Qdrant pack requires embedding_model")
        if len(expected_identity) < 16:
            raise ValueError("Qdrant pack requires embedding_space_identity")
        if dimensions < 1 or dimensions > 65536:
            raise ValueError("Qdrant pack requires valid embedding_dimensions")
        if vector_name and not _COLLECTION_RE.fullmatch(vector_name):
            raise ValueError("Qdrant vector_name is invalid")
        return collection, embedding_model, dimensions, vector_name

    def search(
        self,
        pack: KnowledgePack,
        query: str,
        *,
        limit: int = 8,
    ) -> list[KnowledgeHit]:
        if pack.kind not in {"qdrant", "qdrant_edge"}:
            raise ValueError("Qdrant backend requires a qdrant/qdrant_edge pack")
        KnowledgeFabric._validate_qdrant_endpoint(pack.location)
        collection, embedding_model, dimensions, vector_name = self._metadata(pack)
        client = self.embedding_client_factory(embedding_model)
        identity = client.embedding_identity(refresh=True)
        actual_identity = self._fingerprint(identity)
        expected_identity = str(
            (pack.metadata or {}).get("embedding_space_identity") or ""
        ).strip()
        if not actual_identity or actual_identity != expected_identity:
            raise EmbeddingSpaceMismatch(
                "Qdrant embedding-space identity mismatch; rebuild/reconfigure required"
            )

        vector = [float(value) for value in list(client.embed(str(query)))[:65536]]
        if len(vector) != dimensions:
            raise EmbeddingSpaceMismatch(
                "Qdrant embedding dimension mismatch; rebuild/reconfigure required"
            )

        payload: dict[str, Any] = {
            "query": vector,
            "limit": max(1, min(50, int(limit))),
            "with_payload": True,
            "with_vector": False,
        }
        if vector_name:
            payload["using"] = vector_name

        endpoint = (
            pack.location.rstrip("/")
            + "/collections/"
            + quote(collection, safe="")
            + "/points/query"
        )
        response = self.request_json(endpoint, payload)
        result = response.get("result")
        points = (
            list(result.get("points") or [])
            if isinstance(result, dict)
            else []
        )

        output: list[KnowledgeHit] = []
        for raw in points[: max(1, min(50, int(limit)))]:
            if not isinstance(raw, dict):
                continue
            data = raw.get("payload")
            data = dict(data) if isinstance(data, dict) else {}
            snippet = next(
                (
                    " ".join(str(data.get(key) or "").split())
                    for key in ("text", "content", "page_content", "snippet", "body")
                    if str(data.get(key) or "").strip()
                ),
                "",
            )[:1200]
            if not snippet:
                continue
            title = next(
                (
                    " ".join(str(data.get(key) or "").split())
                    for key in ("title", "name", "heading")
                    if str(data.get(key) or "").strip()
                ),
                pack.title,
            )[:240]
            locator = next(
                (
                    " ".join(str(data.get(key) or "").split())
                    for key in ("locator", "path", "url", "source")
                    if str(data.get(key) or "").strip()
                ),
                str(raw.get("id") or ""),
            )[:500]
            content_hash = str(data.get("content_hash") or "").strip()[:128]
            if not content_hash:
                content_hash = sha256(snippet.encode("utf-8")).hexdigest()
            try:
                score = float(raw.get("score", 0.0) or 0.0)
            except (TypeError, ValueError):
                score = 0.0
            output.append(KnowledgeHit(
                pack_id=pack.id,
                title=title,
                snippet=snippet,
                source=f"{pack.title} / Qdrant",
                score=score,
                locator=locator,
                content_hash=content_hash,
                collection=pack.collection,
                source_date=str(
                    data.get("source_date")
                    or data.get("modified_at")
                    or data.get("date")
                    or ""
                )[:80],
                indexed_at=str(data.get("indexed_at") or "")[:80],
                citation_id=f"knowledge:{pack.id}:{content_hash[:16]}",
            ))
        return output

    def status(self) -> dict[str, Any]:
        return {
            "version": self.VERSION,
            "mode": "read_only_query",
            "local_private_only": True,
            "embedding_identity_required": True,
            "authority": "derived semantic retrieval only",
        }
