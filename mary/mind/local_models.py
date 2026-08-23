"""Hardware-conscious local model catalog and Ollama benchmark helpers.

The catalog is deliberately role-oriented: local models are candidate organs
for Mary, not replacements for Mary's identity.  Live measurements on the
creator's current host decide whether a model is useful.
"""
from __future__ import annotations

from dataclasses import dataclass
import json
import os
from time import monotonic
import urllib.request
from typing import Any


@dataclass(frozen=True)
class LocalModelCandidate:
    model: str
    role: str
    approx_size_gb: float
    notes: str
    priority: int
    tier: str = "extended"

    def to_dict(self) -> dict[str, Any]:
        return {
            "model": self.model,
            "role": self.role,
            "approx_size_gb": self.approx_size_gb,
            "notes": self.notes,
            "priority": self.priority,
            "tier": self.tier,
        }


# Conservative candidates for a 32 GB RAM / 4 GB VRAM-class host. Sizes are
# approximate Ollama downloads and informational only.  A 4 GB GPU can still
# use system RAM / partial offload, so slower 3-4B candidates remain useful for
# non-critical specialist roles.
CANDIDATES: tuple[LocalModelCandidate, ...] = (
    LocalModelCandidate("qwen3:1.7b", "character_verbalizer", 1.4, "First candidate for Mary's small local language cortex; same family as the known 4B character baseline.", 1, "minimal"),
    LocalModelCandidate("llama3.2:1b", "fast_rewrite", 1.3, "Very small dialogue/rewrite/retrieval candidate for latency-sensitive local wording.", 2, "minimal"),
    LocalModelCandidate("gemma3:1b", "utility", 0.815, "Tiny extraction/summarization/classification utility candidate.", 3, "minimal"),
    LocalModelCandidate("smollm2:1.7b", "light_dialogue", 1.8, "Compact on-device dialogue alternative; useful as a speed/quality comparison, not an identity source.", 4, "extended"),
    LocalModelCandidate("llama3.2:3b", "general_dialogue", 2.0, "Compact general dialogue/retrieval/summarization candidate.", 5, "extended"),
    LocalModelCandidate("phi4-mini", "local_reasoning", 2.5, "Reasoning-focused candidate; keep outside the reflex path and benchmark for structured tasks.", 6, "extended"),
    LocalModelCandidate("qwen3:4b", "rich_character", 2.5, "Known Mary-like quality baseline; retain as a character reference even when too slow for front-line chat.", 7, "baseline"),
    LocalModelCandidate("nomic-embed-text", "embeddings", 0.274, "Optional reservoir embedding model; basic SQLite FTS retrieval does not depend on it.", 8, "optional"),
)


class OllamaModelLab:
    def __init__(self, base_url: str | None = None, timeout: float = 60.0) -> None:
        self.base_url = (base_url or os.getenv("MARY_OLLAMA_BASE_URL", "http://localhost:11434")).rstrip("/")
        self.timeout = max(2.0, float(timeout))

    def installed(self) -> set[str]:
        request = urllib.request.Request(f"{self.base_url}/api/tags", headers={"Accept": "application/json"})
        with urllib.request.urlopen(request, timeout=2.0) as response:
            payload = json.loads(response.read().decode("utf-8"))
        output: set[str] = set()
        for item in payload.get("models") or []:
            if isinstance(item, dict):
                name = str(item.get("name") or item.get("model") or "").strip()
                if name:
                    output.add(name)
                    output.add(name.split(":latest")[0])
        return output

    def benchmark(self, model: str, prompt: str, *, max_tokens: int = 80, think: bool = False, keep_alive: str = "10m") -> dict[str, Any]:
        body = json.dumps({
            "model": model,
            "messages": [{"role": "user", "content": prompt}],
            "stream": False,
            "think": bool(think),
            "keep_alive": str(keep_alive),
            "options": {"temperature": 0.55, "num_predict": int(max_tokens), "num_ctx": 2048},
        }).encode("utf-8")
        request = urllib.request.Request(
            f"{self.base_url}/api/chat",
            data=body,
            headers={"Content-Type": "application/json", "Accept": "application/json"},
            method="POST",
        )
        started = monotonic()
        with urllib.request.urlopen(request, timeout=self.timeout) as response:
            payload = json.loads(response.read().decode("utf-8"))
        wall_ms = (monotonic() - started) * 1000.0
        eval_count = int(payload.get("eval_count") or 0)
        eval_duration_ns = int(payload.get("eval_duration") or 0)
        prompt_eval_count = int(payload.get("prompt_eval_count") or 0)
        load_duration_ns = int(payload.get("load_duration") or 0)
        prompt_eval_duration_ns = int(payload.get("prompt_eval_duration") or 0)
        total_duration_ns = int(payload.get("total_duration") or 0)
        tokens_per_second = 0.0
        if eval_count > 0 and eval_duration_ns > 0:
            tokens_per_second = eval_count / (eval_duration_ns / 1_000_000_000.0)
        return {
            "model": model,
            "wall_ms": round(wall_ms, 2),
            "total_ms": round(total_duration_ns / 1_000_000.0, 2),
            "load_ms": round(load_duration_ns / 1_000_000.0, 2),
            "prompt_eval_ms": round(prompt_eval_duration_ns / 1_000_000.0, 2),
            "prompt_tokens": prompt_eval_count,
            "completion_tokens": eval_count,
            "tokens_per_second": round(tokens_per_second, 2),
            "response": str((payload.get("message") or {}).get("content") or "").strip(),
        }

    @staticmethod
    def catalog() -> list[dict[str, Any]]:
        return [candidate.to_dict() for candidate in CANDIDATES]
