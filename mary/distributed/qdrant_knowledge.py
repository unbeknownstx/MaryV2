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
from uuid import NAMESPACE_URL, uuid5
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



class QdrantKnowledgeIndexer(QdrantKnowledgeBackend):
    """Explicit derived-index writer; never runs during Mary startup."""

    INDEX_VERSION = 1

    def __init__(
        self,
        *,
        embedding_client_factory: Callable[[str], Any] | None = None,
        request_json: Callable[[str, dict[str, Any]], dict[str, Any]] | None = None,
        write_json: Callable[
            [str, str, dict[str, Any]], dict[str, Any]
        ] | None = None,
        timeout: float = 15.0,
    ) -> None:
        super().__init__(
            embedding_client_factory=embedding_client_factory,
            request_json=request_json,
            timeout=timeout,
        )
        self.write_json = write_json or self._write_json

    def _write_json(
        self,
        method: str,
        url: str,
        payload: dict[str, Any],
    ) -> dict[str, Any]:
        request = Request(
            url,
            data=json.dumps(payload).encode("utf-8"),
            headers={
                "Accept": "application/json",
                "Content-Type": "application/json",
                "User-Agent": "MaryV2-QdrantKnowledgeIndexer/1",
            },
            method=str(method).upper(),
        )
        with urlopen(request, timeout=self.timeout) as response:  # nosec B310 - endpoint is validated local/private
            raw = response.read(4 * 1024 * 1024)
        decoded = json.loads(raw.decode("utf-8"))
        return dict(decoded) if isinstance(decoded, dict) else {}

    def _verified_embedding(
        self,
        pack: KnowledgePack,
    ) -> tuple[Any, str, int, str, str]:
        KnowledgeFabric._validate_qdrant_endpoint(pack.location)
        collection, model, dimensions, vector_name = self._metadata(pack)
        client = self.embedding_client_factory(model)
        actual = self._fingerprint(
            client.embedding_identity(refresh=True)
        )
        expected = str(
            (pack.metadata or {}).get("embedding_space_identity") or ""
        ).strip()
        if not actual or actual != expected:
            raise EmbeddingSpaceMismatch(
                "Qdrant embedding-space identity mismatch; rebuild/reconfigure required"
            )
        probe = [float(value) for value in list(
            client.embed("MaryV2 vector index preflight")
        )[:65536]]
        if len(probe) != dimensions:
            raise EmbeddingSpaceMismatch(
                "Qdrant embedding dimension mismatch; rebuild/reconfigure required"
            )
        return client, collection, dimensions, vector_name, actual

    def create_collection(self, pack: KnowledgePack) -> dict[str, Any]:
        _client, collection, dimensions, vector_name, identity = (
            self._verified_embedding(pack)
        )
        vector_config: dict[str, Any]
        if vector_name:
            vector_config = {
                vector_name: {
                    "size": dimensions,
                    "distance": "Cosine",
                }
            }
        else:
            vector_config = {
                "size": dimensions,
                "distance": "Cosine",
            }
        url = (
            pack.location.rstrip("/")
            + "/collections/"
            + quote(collection, safe="")
        )
        response = self.write_json(
            "PUT",
            url,
            {
                "vectors": vector_config,
                "on_disk_payload": True,
            },
        )
        return {
            "ok": True,
            "pack_id": pack.id,
            "collection": collection,
            "dimensions": dimensions,
            "vector_name": vector_name,
            "embedding_space_identity": identity,
            "response_status": str(response.get("status") or "")[:80],
            "authority": "derived local vector index only",
        }

    def reconcile(
        self,
        pack: KnowledgePack,
        fabric: KnowledgeFabric,
        *,
        source_pack_id: str = "",
    ) -> dict[str, Any]:
        """Compare source/index/build accounting without mutating Qdrant."""

        KnowledgeFabric._validate_qdrant_endpoint(pack.location)
        collection, _model, _dimensions, _vector_name = self._metadata(pack)
        source_id = (
            str(source_pack_id or "").strip()
            or str((pack.metadata or {}).get("source_pack_id") or "").strip()
        )
        if not source_id:
            raise ValueError(
                "Qdrant reconciliation requires source_pack_id metadata or argument"
            )
        source_pack = fabric.get(source_id)
        if source_pack.kind != "local_files":
            raise ValueError("Qdrant reconciliation source must be local_files")
        active_chunks = fabric.indexed_chunks(
            source_id,
            enabled_only=True,
            limit=20_000,
        )
        build = dict((pack.metadata or {}).get("vector_build") or {})
        recorded_vectors = max(0, int(build.get("vectors") or 0))
        recorded_source_fingerprint = str(
            build.get("source_fingerprint") or ""
        ).strip()
        rebuild_id = str(build.get("rebuild_id") or "").strip()

        endpoint = (
            pack.location.rstrip("/")
            + "/collections/"
            + quote(collection, safe="")
            + "/points/count"
        )
        count_all = self.request_json(
            endpoint,
            {
                "filter": {
                    "must": [{
                        "key": "mary_vector_pack_id",
                        "match": {"value": pack.id},
                    }],
                },
                "exact": True,
            },
        )
        actual_vectors = max(
            0,
            int(dict(count_all.get("result") or {}).get("count") or 0),
        )
        generation_vectors = 0
        if rebuild_id:
            count_generation = self.request_json(
                endpoint,
                {
                    "filter": {
                        "must": [
                            {
                                "key": "mary_vector_pack_id",
                                "match": {"value": pack.id},
                            },
                            {
                                "key": "mary_rebuild_id",
                                "match": {"value": rebuild_id},
                            },
                        ],
                    },
                    "exact": True,
                },
            )
            generation_vectors = max(
                0,
                int(dict(count_generation.get("result") or {}).get("count") or 0),
            )

        source_current = bool(
            source_pack.content_fingerprint
            and recorded_source_fingerprint
            and source_pack.content_fingerprint == recorded_source_fingerprint
        )
        expected = len(active_chunks)
        generation_complete = bool(
            rebuild_id
            and generation_vectors == expected
            and recorded_vectors == expected
        )
        stale_vectors = max(0, actual_vectors - generation_vectors)
        healthy = bool(
            source_current
            and generation_complete
            and actual_vectors == generation_vectors
        )
        if healthy:
            state = "healthy"
        elif not build:
            state = "not_built"
        elif not source_current:
            state = "source_changed"
        elif generation_vectors < expected:
            state = "incomplete"
        elif stale_vectors > 0 or actual_vectors != recorded_vectors:
            state = "stale_or_mismatched_vectors"
        else:
            state = "mismatch"

        return {
            "ok": healthy,
            "state": state,
            "pack_id": pack.id,
            "source_pack_id": source_id,
            "source_chunks_expected": expected,
            "recorded_vectors": recorded_vectors,
            "actual_vectors": actual_vectors,
            "current_generation_vectors": generation_vectors,
            "stale_or_other_generation_vectors": stale_vectors,
            "source_fingerprint_current": source_current,
            "generation_complete": generation_complete,
            "repair": (
                "none"
                if healthy
                else "explicit qdrant-rebuild after reviewing source refresh state"
            ),
            "mutation_performed": False,
            "authority": "derived index reconciliation only",
        }

    def rebuild(
        self,
        pack: KnowledgePack,
        fabric: KnowledgeFabric,
        *,
        source_pack_id: str = "",
        limit: int = 20_000,
        batch_size: int = 32,
    ) -> dict[str, Any]:
        client, collection, dimensions, vector_name, identity = (
            self._verified_embedding(pack)
        )
        source_id = (
            str(source_pack_id or "").strip()
            or str((pack.metadata or {}).get("source_pack_id") or "").strip()
        )
        if not source_id:
            raise ValueError(
                "Qdrant rebuild requires source_pack_id metadata or argument"
            )
        source_pack = fabric.get(source_id)
        if source_pack.kind != "local_files":
            raise ValueError("Qdrant rebuild source must be a local_files pack")
        if not source_pack.content_fingerprint:
            raise RuntimeError(
                "source local_files pack must be indexed before Qdrant rebuild"
            )
        chunks = fabric.indexed_chunks(
            source_id,
            enabled_only=True,
            limit=limit,
        )
        rebuild_id = sha256(
            (
                source_pack.content_fingerprint
                + "|"
                + identity
                + "|"
                + str(dimensions)
                + "|"
                + vector_name
            ).encode("utf-8")
        ).hexdigest()

        endpoint = (
            pack.location.rstrip("/")
            + "/collections/"
            + quote(collection, safe="")
        )
        bounded_batch = max(1, min(128, int(batch_size)))
        indexed = 0
        batches = 0
        errors = 0

        for offset in range(0, len(chunks), bounded_batch):
            rows = chunks[offset : offset + bounded_batch]
            points: list[dict[str, Any]] = []
            try:
                for row in rows:
                    text = str(row.get("text") or "")
                    vector = [
                        float(value)
                        for value in list(client.embed(text))[:65536]
                    ]
                    if len(vector) != dimensions:
                        raise EmbeddingSpaceMismatch(
                            "Qdrant embedding dimension changed during rebuild"
                        )
                    content_hash = str(
                        row.get("content_hash") or sha256(
                            text.encode("utf-8")
                        ).hexdigest()
                    )[:128]
                    point_id = str(uuid5(
                        NAMESPACE_URL,
                        (
                            "maryv2-knowledge:"
                            + pack.id
                            + ":"
                            + str(row.get("locator") or "")
                            + ":"
                            + content_hash
                        ),
                    ))
                    vector_payload: Any = (
                        {vector_name: vector}
                        if vector_name
                        else vector
                    )
                    points.append({
                        "id": point_id,
                        "vector": vector_payload,
                        "payload": {
                            "mary_vector_pack_id": pack.id,
                            "mary_source_pack_id": source_id,
                            "mary_rebuild_id": rebuild_id,
                            "embedding_space_identity": identity,
                            "title": str(row.get("title") or "")[:240],
                            "text": text[:20_000],
                            "locator": str(row.get("locator") or "")[:500],
                            "content_hash": content_hash,
                            "source_date": str(row.get("source_date") or "")[:80],
                            "indexed_at": str(row.get("indexed_at") or "")[:80],
                        },
                    })
            except Exception:
                errors += 1
                break

            self.write_json(
                "PUT",
                endpoint + "/points?wait=true",
                {"points": points},
            )
            indexed += len(points)
            batches += 1

        # Never remove the previous successful generation unless every current
        # chunk was embedded and upserted. An interrupted rebuild stays usable.
        stale_deleted = False
        if errors == 0 and indexed == len(chunks):
            self.write_json(
                "POST",
                endpoint + "/points/delete?wait=true",
                {
                    "filter": {
                        "must": [{
                            "key": "mary_vector_pack_id",
                            "match": {"value": pack.id},
                        }],
                        "must_not": [{
                            "key": "mary_rebuild_id",
                            "match": {"value": rebuild_id},
                        }],
                    }
                },
            )
            stale_deleted = True
            fabric.record_vector_build(
                pack.id,
                source_pack_id=source_id,
                source_fingerprint=source_pack.content_fingerprint,
                embedding_space_identity=identity,
                vectors=indexed,
                rebuild_id=rebuild_id,
            )

        return {
            "ok": bool(errors == 0 and indexed == len(chunks)),
            "pack_id": pack.id,
            "source_pack_id": source_id,
            "source_chunks": len(chunks),
            "vectors_indexed": indexed,
            "batches": batches,
            "errors": errors,
            "stale_generation_deleted": stale_deleted,
            "rebuild_id": rebuild_id,
            "embedding_space_identity": identity,
            "dimensions": dimensions,
            "authority": "rebuildable derived semantic index only",
        }
