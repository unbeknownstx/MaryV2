"""Benchmark Mary's real SemanticVectorIndex query path with synthetic data.

This never reads or writes Mary's live reservoir or memory. It compares the
reference Python cosine path with the optional sqlite-vec path and reports p50 /
p95 latency plus sampled ranking parity.

Examples:
    python -m scripts.benchmark_semantic_retrieval --sizes 1000,10000 --queries 30
    python -m scripts.benchmark_semantic_retrieval --sizes 1000,10000,50000 --dimensions 128
"""
from __future__ import annotations

import argparse
import json
import math
import random
from statistics import median
from time import perf_counter
from typing import Any

from mary.mind.vector_index import SemanticVectorIndex


MODEL = "benchmark-embed"
IDENTITY = "benchmark:synthetic-v1"


def _percentile(values: list[float], percentile: float) -> float:
    if not values:
        return 0.0
    ordered = sorted(values)
    position = (len(ordered) - 1) * percentile
    lower = int(math.floor(position))
    upper = int(math.ceil(position))
    if lower == upper:
        return ordered[lower]
    weight = position - lower
    return ordered[lower] * (1.0 - weight) + ordered[upper] * weight


def _unit_vector(rng: random.Random, dimensions: int) -> list[float]:
    values = [rng.uniform(-1.0, 1.0) for _ in range(dimensions)]
    norm = math.sqrt(sum(value * value for value in values)) or 1.0
    return [value / norm for value in values]


def _seed(index: SemanticVectorIndex, *, size: int, dimensions: int, seed: int) -> list[list[float]]:
    rng = random.Random(seed)
    vectors: list[list[float]] = []
    index.register_identity(model=MODEL, embedding_identity=IDENTITY)
    for offset in range(size):
        vector = _unit_vector(rng, dimensions)
        vectors.append(vector)
        index.upsert(
            record_id=f"record-{offset:07d}",
            model=MODEL,
            embedding_identity=IDENTITY,
            vector=vector,
            content=f"synthetic benchmark record {offset}",
        )
    return vectors


def _measure(index: SemanticVectorIndex, queries: list[list[float]], *, limit: int) -> tuple[list[float], list[list[str]]]:
    latencies_ms: list[float] = []
    rankings: list[list[str]] = []
    for query in queries:
        started = perf_counter()
        hits = index.search(
            query,
            model=MODEL,
            embedding_identity=IDENTITY,
            limit=limit,
        )
        latencies_ms.append((perf_counter() - started) * 1000.0)
        rankings.append([hit.record_id for hit in hits])
    return latencies_ms, rankings


def _run_backend(*, backend: str, size: int, dimensions: int, query_count: int, limit: int, seed: int) -> dict[str, Any]:
    # Expand the Python reference scan to the whole synthetic corpus so ranking
    # parity compares the same candidate set as native exact KNN. Production may
    # keep a smaller MARY_VECTOR_MAX_SCAN when the accelerator is unavailable.
    index = SemanticVectorIndex(None, backend=backend, max_scan=max(5000, size))
    build_started = perf_counter()
    vectors = _seed(index, size=size, dimensions=dimensions, seed=seed)
    build_ms = (perf_counter() - build_started) * 1000.0

    rng = random.Random(seed + 1)
    queries = [vectors[rng.randrange(len(vectors))] for _ in range(query_count)]
    latencies, rankings = _measure(index, queries, limit=limit)
    status = index.status(model=MODEL, embedding_identity=IDENTITY)
    result = {
        "requested_backend": backend,
        "active_backend": status["backend"]["active"],
        "backend_error": status["backend"]["last_error"],
        "sqlite_vec_version": status["backend"]["sqlite_vec_version"],
        "size": size,
        "dimensions": dimensions,
        "queries": query_count,
        "limit": limit,
        "build_ms": round(build_ms, 3),
        "query_ms": {
            "min": round(min(latencies), 4) if latencies else 0.0,
            "p50": round(median(latencies), 4) if latencies else 0.0,
            "p95": round(_percentile(latencies, 0.95), 4),
            "max": round(max(latencies), 4) if latencies else 0.0,
        },
        "rankings": rankings,
    }
    index.close()
    return result


def benchmark(*, sizes: list[int], dimensions: int, query_count: int, limit: int, seed: int) -> dict[str, Any]:
    runs: list[dict[str, Any]] = []
    for size in sizes:
        reference = _run_backend(
            backend="python", size=size, dimensions=dimensions,
            query_count=query_count, limit=limit, seed=seed,
        )
        accelerated = _run_backend(
            backend="sqlite_vec", size=size, dimensions=dimensions,
            query_count=query_count, limit=limit, seed=seed,
        )
        accelerated["ranking_parity"] = accelerated["rankings"] == reference["rankings"]
        reference.pop("rankings", None)
        accelerated.pop("rankings", None)
        runs.append({"python": reference, "accelerated": accelerated})
    return {
        "synthetic_only": True,
        "authority": "derived retrieval performance only; no live Mary state touched",
        "runs": runs,
    }


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--sizes", default="1000,10000", help="comma-separated synthetic index sizes")
    parser.add_argument("--dimensions", type=int, default=64)
    parser.add_argument("--queries", type=int, default=25)
    parser.add_argument("--limit", type=int, default=8)
    parser.add_argument("--seed", type=int, default=1337)
    parser.add_argument("--json", action="store_true", dest="json_only")
    args = parser.parse_args()

    sizes = [max(1, int(item.strip())) for item in str(args.sizes).split(",") if item.strip()]
    result = benchmark(
        sizes=sizes,
        dimensions=max(2, min(4096, int(args.dimensions))),
        query_count=max(1, min(500, int(args.queries))),
        limit=max(1, min(50, int(args.limit))),
        seed=int(args.seed),
    )
    print(json.dumps(result, indent=2, sort_keys=True))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
