"""Optional Ollama embedding helper for future semantic reservoir enrichment.

The 12.12 critical path intentionally uses SQLite FTS5 because it is instant,
portable, and dependency-free.  This adapter lets an installed embedding model
(such as nomic-embed-text) be used by explicit maintenance/benchmark jobs
without making Ollama a startup requirement.
"""
from __future__ import annotations

import json
import os
import urllib.error
import urllib.request
from typing import Any


class OllamaEmbeddingClient:
    def __init__(self, *, base_url: str | None = None, model: str | None = None, timeout: float = 15.0) -> None:
        self.base_url = (base_url or os.getenv("MARY_OLLAMA_BASE_URL", "http://localhost:11434")).rstrip("/")
        self.model = model or os.getenv("MARY_OLLAMA_EMBED_MODEL", "nomic-embed-text")
        self.timeout = max(1.0, float(timeout))

    def embed(self, text: str) -> list[float]:
        body = json.dumps({"model": self.model, "input": str(text)}).encode("utf-8")
        request = urllib.request.Request(
            f"{self.base_url}/api/embed",
            data=body,
            headers={"Content-Type": "application/json", "Accept": "application/json"},
            method="POST",
        )
        with urllib.request.urlopen(request, timeout=self.timeout) as response:
            payload: dict[str, Any] = json.loads(response.read().decode("utf-8"))
        embeddings = payload.get("embeddings") or []
        if not embeddings or not isinstance(embeddings[0], list):
            return []
        return [float(value) for value in embeddings[0]]

    def available(self) -> bool:
        try:
            request = urllib.request.Request(f"{self.base_url}/api/tags", headers={"Accept": "application/json"})
            with urllib.request.urlopen(request, timeout=1.0) as response:
                return 200 <= int(response.status) < 300
        except Exception:
            return False
