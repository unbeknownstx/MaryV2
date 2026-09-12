"""Optional Ollama embedding helper with explicit embedding-space identity.

Semantic vectors are rebuildable derived state.  The identity helpers in this
module fingerprint the actual embedding space closely enough that MaryV2 can
refuse to compare vectors produced by a different model artifact/runtime even
when the human-readable model tag did not change.
"""
from __future__ import annotations

from dataclasses import dataclass, asdict
import hashlib
import json
import os
import urllib.request
from typing import Any


@dataclass(frozen=True)
class EmbeddingIdentity:
    provider: str
    model: str
    model_digest: str = ""
    backend: str = "ollama"
    backend_version: str = ""
    protocol: str = "api/embed"
    normalization: str = "raw_cosine"
    revision: str = "mary-embedding-identity-v1"

    def payload(self) -> dict[str, str]:
        return {key: str(value or "") for key, value in asdict(self).items()}

    @property
    def fingerprint(self) -> str:
        canonical = json.dumps(self.payload(), sort_keys=True, separators=(",", ":"), ensure_ascii=True)
        return hashlib.sha256(canonical.encode("utf-8")).hexdigest()

    def to_dict(self) -> dict[str, str]:
        return {**self.payload(), "fingerprint": self.fingerprint}


class OllamaEmbeddingClient:
    def __init__(self, *, base_url: str | None = None, model: str | None = None, timeout: float = 15.0) -> None:
        self.base_url = (base_url or os.getenv("MARY_OLLAMA_BASE_URL", "http://localhost:11434")).rstrip("/")
        self.model = model or os.getenv("MARY_OLLAMA_EMBED_MODEL", "nomic-embed-text")
        self.timeout = max(1.0, float(timeout))
        self._identity_cache: EmbeddingIdentity | None = None

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

    def _model_catalog(self) -> list[dict[str, Any]]:
        try:
            request = urllib.request.Request(f"{self.base_url}/api/tags", headers={"Accept": "application/json"})
            with urllib.request.urlopen(request, timeout=1.0) as response:
                payload: dict[str, Any] = json.loads(response.read().decode("utf-8"))
            return [dict(item) for item in list(payload.get("models") or []) if isinstance(item, dict)]
        except Exception:
            return []

    def list_models(self) -> list[str]:
        output: list[str] = []
        for item in self._model_catalog():
            name = str(item.get("name") or item.get("model") or "").strip()
            if name:
                output.append(name)
        return output

    def model_info(self) -> dict[str, Any]:
        target = self.model.strip().lower()
        target_base = target.split(":", 1)[0]
        exact: dict[str, Any] | None = None
        base_match: dict[str, Any] | None = None
        for item in self._model_catalog():
            name = str(item.get("name") or item.get("model") or "").strip().lower()
            if not name:
                continue
            if name == target:
                exact = item
                break
            if base_match is None and name.split(":", 1)[0] == target_base:
                base_match = item
        return dict(exact or base_match or {})

    def service_version(self) -> str:
        try:
            request = urllib.request.Request(f"{self.base_url}/api/version", headers={"Accept": "application/json"})
            with urllib.request.urlopen(request, timeout=1.0) as response:
                payload: dict[str, Any] = json.loads(response.read().decode("utf-8"))
            return str(payload.get("version") or "").strip()
        except Exception:
            return ""

    def embedding_identity(self, *, refresh: bool = False) -> EmbeddingIdentity:
        if self._identity_cache is not None and not refresh:
            return self._identity_cache
        info = self.model_info()
        digest = str(info.get("digest") or "").strip()
        canonical_model = str(info.get("name") or info.get("model") or self.model).strip() or self.model
        identity = EmbeddingIdentity(
            provider="ollama",
            model=canonical_model,
            model_digest=digest,
            backend="ollama",
            backend_version=self.service_version(),
            protocol="api/embed",
            normalization="raw_cosine",
        )
        self._identity_cache = identity
        return identity

    def available(self) -> bool:
        try:
            request = urllib.request.Request(f"{self.base_url}/api/tags", headers={"Accept": "application/json"})
            with urllib.request.urlopen(request, timeout=1.0) as response:
                return 200 <= int(response.status) < 300
        except Exception:
            return False

    def model_available(self) -> bool:
        target = self.model.strip().lower()
        target_base = target.split(":", 1)[0]
        for name in self.list_models():
            normalized = name.strip().lower()
            if normalized == target or normalized.split(":", 1)[0] == target_base:
                return True
        return False
