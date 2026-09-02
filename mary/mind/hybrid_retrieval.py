"""Hybrid lexical + embedding retrieval over Mary's cognitive reservoir."""
from __future__ import annotations

from dataclasses import replace
import os
from pathlib import Path
from time import monotonic
from typing import Any, Iterable

from .embeddings import OllamaEmbeddingClient
from .reservoir import CognitiveReservoir, ReservoirHit, ReservoirRecord
from .vector_index import SemanticVectorIndex, content_hash
from .contextual_reranker import ContextualReservoirReranker


_TRUE = {"1", "true", "yes", "on", "enabled"}
_FALSE = {"0", "false", "no", "off", "disabled"}


class HybridReservoirRetriever:
    """Blend FTS/lexical candidates with optional semantic vector candidates.

    Vector retrieval is lazy. In ``auto`` mode no Ollama call happens until a
    vector index actually exists. This preserves Mary's fast 13.0 path on
    current hardware while making semantic recall available after an explicit
    index build.
    """

    VERSION = "13.1"

    def __init__(
        self,
        reservoir: CognitiveReservoir,
        *,
        vector_index: SemanticVectorIndex | None = None,
        embedding_client: OllamaEmbeddingClient | None = None,
    ) -> None:
        self.reservoir = reservoir
        self.vector_index = vector_index or SemanticVectorIndex.in_memory()
        self.embedding_client = embedding_client or OllamaEmbeddingClient(timeout=10.0)
        self.mode = os.getenv("MARY_VECTOR_RETRIEVAL", "auto").strip().lower() or "auto"
        self.lexical_weight = self._env_float("MARY_RETRIEVAL_LEXICAL_WEIGHT", 0.62, 0.0, 1.0)
        self.vector_weight = self._env_float("MARY_RETRIEVAL_VECTOR_WEIGHT", 0.38, 0.0, 1.0)
        total = self.lexical_weight + self.vector_weight
        if total <= 0:
            self.lexical_weight, self.vector_weight = 1.0, 0.0
        else:
            self.lexical_weight /= total
            self.vector_weight /= total
        self._last_vector_error: str | None = None
        self._last_query_used_vectors = False
        self._last_build: dict[str, Any] = {}
        self._availability_cache: tuple[float, bool] = (0.0, False)
        self.contextual_reranker = ContextualReservoirReranker()

    @staticmethod
    def _env_float(name: str, default: float, minimum: float, maximum: float) -> float:
        try:
            value = float(os.getenv(name, str(default)) or default)
        except (TypeError, ValueError):
            value = float(default)
        return max(minimum, min(maximum, value))

    def configure_vector_index(self, path: str | Path | None) -> None:
        old = self.vector_index
        self.vector_index = SemanticVectorIndex(
            path,
            max_scan=int(os.getenv("MARY_VECTOR_MAX_SCAN", "5000") or 5000),
        )
        try:
            old.close()
        except Exception:
            pass

    def close(self) -> None:
        try:
            self.vector_index.close()
        except Exception:
            pass

    def vectors_requested(self) -> bool:
        if self.mode in _FALSE:
            return False
        if self.mode in _TRUE:
            return True
        # auto: use semantic search only after an index has been explicitly built
        return self.vector_index.count(model=self.embedding_client.model) > 0

    def embedding_available(self, *, refresh: bool = False) -> bool:
        now = monotonic()
        cached_at, cached = self._availability_cache
        if not refresh and (now - cached_at) < 30.0:
            return cached
        try:
            available = bool(self.embedding_client.model_available())
        except Exception:
            available = False
        self._availability_cache = (now, available)
        return available

    def search(
        self,
        query: str,
        *,
        limit: int = 5,
        minimum_confidence: float = 0.65,
        context: dict[str, Any] | None = None,
    ) -> list[ReservoirHit]:
        limit = max(1, min(25, int(limit)))
        lexical = self.reservoir.search(query, limit=max(limit * 2, 8), minimum_confidence=minimum_confidence)
        by_id: dict[str, ReservoirHit] = {hit.record_id: hit for hit in lexical}
        lexical_scores = {hit.record_id: max(0.0, min(1.0, float(hit.score))) for hit in lexical}
        vector_scores: dict[str, float] = {}
        self._last_query_used_vectors = False

        if self.vectors_requested() and self.embedding_available():
            try:
                query_vector = self.embedding_client.embed(query)
                if query_vector:
                    for vector_hit in self.vector_index.search(
                        query_vector,
                        model=self.embedding_client.model,
                        limit=max(limit * 3, 12),
                    ):
                        record = self.reservoir.get(vector_hit.record_id)
                        if record is None:
                            continue
                        if content_hash(record.content) != vector_hit.content_hash:
                            continue
                        if record.confidence < minimum_confidence:
                            continue
                        by_id.setdefault(record.record_id, record)
                        # Cosine [-1,1] -> relevance [0,1]. Negative matches are
                        # not useful for candidate recall.
                        vector_scores[record.record_id] = max(0.0, min(1.0, (vector_hit.score + 1.0) / 2.0))
                    self._last_query_used_vectors = bool(vector_scores)
                self._last_vector_error = None
            except Exception as exc:
                self._last_vector_error = f"{type(exc).__name__}: {exc}"

        ranked: list[ReservoirHit] = []
        for rid, hit in by_id.items():
            lexical_score = lexical_scores.get(rid, 0.0)
            vector_score = vector_scores.get(rid, 0.0)
            if vector_score and lexical_score:
                score = self.lexical_weight * lexical_score + self.vector_weight * vector_score
            elif vector_score:
                # Vector-only matches need a slightly stronger bar than lexical
                # hits because semantic similarity is recall, not authority.
                score = 0.86 * vector_score
            else:
                score = lexical_score
            score *= 0.72 + 0.28 * max(0.0, min(1.0, hit.confidence))
            metadata = dict(hit.metadata)
            metadata["retrieval"] = {
                "lexical_score": round(lexical_score, 4),
                "vector_score": round(vector_score, 4),
                "hybrid": bool(vector_score),
            }
            ranked.append(replace(hit, score=score, metadata=metadata))
        ranked.sort(key=lambda item: (item.score, item.confidence), reverse=True)
        if context:
            ranked = self.contextual_reranker.rerank(ranked, context=context, limit=limit)
        return ranked[:limit]

    def rebuild_vectors(self, records: Iterable[ReservoirRecord], *, limit: int | None = None) -> dict[str, Any]:
        materialized = list(records)
        requested_limit = int(
            limit if limit is not None else int(os.getenv("MARY_VECTOR_INDEX_LIMIT", "1000") or 1000)
        )
        requested_limit = max(1, min(20_000, requested_limit))
        selected = materialized[:requested_limit]
        if not self.embedding_available(refresh=True):
            result = {
                "ok": False,
                "indexed": 0,
                "requested": len(selected),
                "model": self.embedding_client.model,
                "reason": "Ollama embedding model is unavailable",
            }
            self._last_build = result
            return result

        indexed = 0
        errors = 0
        for record in selected:
            try:
                vector = self.embedding_client.embed(record.content)
                if vector and self.vector_index.upsert(
                    record_id=record.record_id,
                    model=self.embedding_client.model,
                    vector=vector,
                    content=record.content,
                ):
                    indexed += 1
                else:
                    errors += 1
            except Exception as exc:
                errors += 1
                self._last_vector_error = f"{type(exc).__name__}: {exc}"
        removed = self.vector_index.remove_missing(
            [record.record_id for record in materialized],
            model=self.embedding_client.model,
        )
        result = {
            "ok": indexed > 0 or not selected,
            "indexed": indexed,
            "requested": len(selected),
            "errors": errors,
            "removed_stale": removed,
            "model": self.embedding_client.model,
            "vectors": self.vector_index.count(model=self.embedding_client.model),
        }
        self._last_build = result
        return result

    def status(self) -> dict[str, Any]:
        return {
            "version": self.VERSION,
            "mode": self.mode,
            "vector_requested": self.vectors_requested(),
            "embedding_model": self.embedding_client.model,
            "embedding_available": self.embedding_available() if self.vectors_requested() else False,
            "last_query_used_vectors": self._last_query_used_vectors,
            "last_vector_error": self._last_vector_error,
            "weights": {
                "lexical": round(self.lexical_weight, 3),
                "vector": round(self.vector_weight, 3),
            },
            "vector_index": self.vector_index.status(model=self.embedding_client.model),
            "last_build": dict(self._last_build),
            "semantics": "vectors retrieve candidates; canonical authority/provenance still decides truth",
        }
