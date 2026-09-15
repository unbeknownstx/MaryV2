"""Independent embedding-family routing for MaryV2 13.64.

Embedding failover is deliberately stricter than chat failover: providers may
change, but model family + dimensions + embedding-space identity may not.
"""
from __future__ import annotations
from dataclasses import dataclass
from typing import Callable, Sequence

VERSION = "13.64"

@dataclass(frozen=True)
class EmbeddingRoute:
    provider: str
    family: str
    dimensions: int
    space_identity: str
    ready: bool = True

class EmbeddingRouter:
    def __init__(self, routes: Sequence[EmbeddingRoute]) -> None:
        self.routes = tuple(routes)

    def candidates(self, *, family: str, dimensions: int, space_identity: str) -> tuple[EmbeddingRoute, ...]:
        return tuple(route for route in self.routes if route.ready and route.family == family and route.dimensions == int(dimensions) and route.space_identity == space_identity)

    def execute(self, *, family: str, dimensions: int, space_identity: str, operation: Callable[[EmbeddingRoute], list[list[float]]]) -> list[list[float]]:
        candidates = self.candidates(family=family, dimensions=dimensions, space_identity=space_identity)
        if not candidates:
            raise LookupError("no compatible embedding route")
        last_error: Exception | None = None
        for route in candidates:
            try:
                vectors = operation(route)
                if any(len(vector) != dimensions for vector in vectors):
                    raise ValueError("embedding dimension mismatch")
                return vectors
            except Exception as exc:
                last_error = exc
        raise RuntimeError("compatible embedding providers exhausted") from last_error
