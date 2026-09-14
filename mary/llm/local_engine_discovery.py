"""Bounded discovery for local inference engines.

Mary already has dedicated Ollama/llama.cpp adapters plus a generic
OpenAI-compatible provider. This module discovers reachable loopback endpoints
without granting execution authority or guessing that an ambiguous port proves
a specific engine identity.
"""
from __future__ import annotations

from concurrent.futures import ThreadPoolExecutor, as_completed
from dataclasses import asdict, dataclass
import json
from typing import Any
from urllib.error import HTTPError, URLError
from urllib.parse import urlparse
from urllib.request import HTTPRedirectHandler, Request, build_opener

VERSION = "13.42"


@dataclass(frozen=True)
class LocalEnginePreset:
    engine_id: str
    display_name: str
    base_url: str
    protocol: str = "openai_compatible"
    aliases: tuple[str, ...] = ()
    identity_strength: str = "port_hint"


@dataclass(frozen=True)
class DetectedLocalEngine:
    engine_id: str
    display_name: str
    base_url: str
    protocol: str
    models: tuple[str, ...]
    aliases: tuple[str, ...] = ()
    identity_strength: str = "port_hint"
    reachable: bool = True

    def to_dict(self) -> dict[str, Any]:
        return asdict(self)

    def provider_candidate(self, *, model: str | None = None) -> dict[str, Any]:
        selected = str(model or "").strip()
        if not selected and self.models:
            selected = self.models[0]
        return {
            "adapter": "ollama" if self.protocol == "ollama" else "openai_compatible",
            "provider_name": f"local_{self.engine_id}"[:80],
            "base_url": self.base_url,
            "model": selected,
            "local": True,
            "cost_class": "zero_local",
            "privacy": "local_only",
            "authority": "candidate_only",
        }


PRESETS: tuple[LocalEnginePreset, ...] = (
    LocalEnginePreset(
        "ollama",
        "Ollama",
        "http://127.0.0.1:11434",
        protocol="ollama",
        identity_strength="protocol_specific",
    ),
    LocalEnginePreset(
        "lmstudio",
        "LM Studio candidate",
        "http://127.0.0.1:1234/v1",
        aliases=("LM Studio",),
    ),
    LocalEnginePreset(
        "vllm",
        "vLLM candidate",
        "http://127.0.0.1:8000/v1",
        aliases=("vLLM",),
    ),
    LocalEnginePreset(
        "openai_compat_8080",
        "OpenAI-compatible endpoint :8080",
        "http://127.0.0.1:8080/v1",
        aliases=("llama.cpp", "LocalAI", "TGI"),
        identity_strength="protocol_only",
    ),
    LocalEnginePreset(
        "litellm",
        "LiteLLM candidate",
        "http://127.0.0.1:4000/v1",
        aliases=("LiteLLM",),
    ),
    LocalEnginePreset(
        "koboldcpp",
        "KoboldCpp candidate",
        "http://127.0.0.1:5001/v1",
        aliases=("KoboldCpp",),
    ),
    LocalEnginePreset(
        "openai_compat_5000",
        "OpenAI-compatible endpoint :5000",
        "http://127.0.0.1:5000/v1",
        aliases=("text-generation-webui", "TabbyAPI"),
        identity_strength="protocol_only",
    ),
    LocalEnginePreset(
        "jan",
        "Jan candidate",
        "http://127.0.0.1:1337/v1",
        aliases=("Jan",),
    ),
    LocalEnginePreset(
        "gpt4all",
        "GPT4All candidate",
        "http://127.0.0.1:4891/v1",
        aliases=("GPT4All",),
    ),
    LocalEnginePreset(
        "aphrodite",
        "Aphrodite candidate",
        "http://127.0.0.1:2242/v1",
        aliases=("Aphrodite",),
    ),
    LocalEnginePreset(
        "sglang",
        "SGLang candidate",
        "http://127.0.0.1:30000/v1",
        aliases=("SGLang",),
    ),
    LocalEnginePreset(
        "locally_uncensored_api",
        "Locally Uncensored Local API candidate",
        "http://127.0.0.1:8129/v1",
        aliases=("Locally Uncensored Local API",),
    ),
)


class _NoRedirect(HTTPRedirectHandler):
    def redirect_request(self, req, fp, code, msg, headers, newurl):
        return None


def _is_loopback(value: str) -> bool:
    try:
        parsed = urlparse(str(value or ""))
    except Exception:
        return False
    return (
        parsed.scheme == "http"
        and (parsed.hostname or "").lower() in {"127.0.0.1", "localhost", "::1"}
    )


def _bounded_models(value: Any) -> tuple[str, ...]:
    output: list[str] = []
    rows = value if isinstance(value, list) else []
    for row in rows[:128]:
        if not isinstance(row, dict):
            continue
        name = str(row.get("id") or row.get("name") or row.get("model") or "").strip()
        if not name:
            continue
        name = name[:240]
        if name not in output:
            output.append(name)
    return tuple(output)


def _probe_one(
    preset: LocalEnginePreset,
    *,
    timeout: float = 0.45,
    opener=None,
) -> DetectedLocalEngine | None:
    if not _is_loopback(preset.base_url):
        return None
    timeout = max(0.1, min(1.5, float(timeout)))
    opener = opener or build_opener(_NoRedirect())
    if preset.protocol == "ollama":
        url = preset.base_url.rstrip("/") + "/api/tags"
    else:
        url = preset.base_url.rstrip("/") + "/models"
    request = Request(
        url,
        headers={"Accept": "application/json", "User-Agent": "MaryV2-local-engine-discovery/13.42"},
        method="GET",
    )
    try:
        with opener.open(request, timeout=timeout) as response:
            if not 200 <= int(getattr(response, "status", 0) or 0) < 300:
                return None
            raw = response.read(512_000)
    except (OSError, HTTPError, URLError, TimeoutError):
        return None

    try:
        payload = json.loads(raw.decode("utf-8"))
    except (UnicodeDecodeError, json.JSONDecodeError):
        return None
    if not isinstance(payload, dict):
        return None

    if preset.protocol == "ollama":
        models = _bounded_models(payload.get("models"))
    else:
        models = _bounded_models(payload.get("data"))
    return DetectedLocalEngine(
        engine_id=preset.engine_id,
        display_name=preset.display_name,
        base_url=preset.base_url,
        protocol=preset.protocol,
        models=models,
        aliases=preset.aliases,
        identity_strength=preset.identity_strength,
    )


def discover_local_engines(
    *,
    timeout_per_endpoint: float = 0.45,
    presets: tuple[LocalEnginePreset, ...] = PRESETS,
    max_workers: int = 6,
) -> list[DetectedLocalEngine]:
    """Probe fixed loopback candidates in parallel and return reachable engines.

    Discovery is advisory. It does not register providers, select models, grant
    permissions, start services, download models, or alter Mary routing.
    """
    safe = tuple(preset for preset in presets if _is_loopback(preset.base_url))
    if not safe:
        return []
    workers = max(1, min(8, int(max_workers), len(safe)))
    found: list[DetectedLocalEngine] = []
    with ThreadPoolExecutor(max_workers=workers, thread_name_prefix="MaryEngineProbe") as pool:
        futures = {
            pool.submit(_probe_one, preset, timeout=timeout_per_endpoint): preset
            for preset in safe
        }
        for future in as_completed(futures):
            try:
                item = future.result()
            except Exception:
                item = None
            if item is not None:
                found.append(item)
    return sorted(found, key=lambda item: (item.base_url, item.engine_id))


def discovery_status(engines: list[DetectedLocalEngine] | None = None) -> dict[str, Any]:
    rows = list(engines or [])
    return {
        "version": VERSION,
        "detected": [item.to_dict() for item in rows],
        "count": len(rows),
        "execution_authorized": False,
        "policy": (
            "loopback discovery only; endpoint reachability/model listing is "
            "not engine trust, model quality, or execution permission"
        ),
    }
