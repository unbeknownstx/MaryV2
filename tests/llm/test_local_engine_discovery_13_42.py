from __future__ import annotations

import json

from mary.llm.local_engine_discovery import (
    LocalEnginePreset,
    _probe_one,
    discovery_status,
)


class _Response:
    def __init__(self, payload, status=200):
        self.status = status
        self._raw = json.dumps(payload).encode("utf-8")

    def read(self, limit):
        return self._raw[:limit]

    def __enter__(self):
        return self

    def __exit__(self, *args):
        return False


class _Opener:
    def __init__(self, payload):
        self.payload = payload
        self.requests = []

    def open(self, request, timeout):
        self.requests.append((request.full_url, timeout))
        return _Response(self.payload)


def test_openai_compatible_probe_lists_models_and_stays_candidate_only():
    preset = LocalEnginePreset(
        "lmstudio",
        "LM Studio candidate",
        "http://127.0.0.1:1234/v1",
        aliases=("LM Studio",),
    )
    opener = _Opener({"data": [{"id": "qwen"}, {"id": "gemma"}]})
    found = _probe_one(preset, opener=opener, timeout=0.2)
    assert found is not None
    assert found.models == ("qwen", "gemma")
    assert opener.requests[0][0].endswith("/v1/models")
    candidate = found.provider_candidate()
    assert candidate["authority"] == "candidate_only"
    assert candidate["privacy"] == "local_only"


def test_ollama_uses_protocol_specific_tags_endpoint():
    preset = LocalEnginePreset(
        "ollama",
        "Ollama",
        "http://127.0.0.1:11434",
        protocol="ollama",
        identity_strength="protocol_specific",
    )
    opener = _Opener({"models": [{"name": "qwen3:4b"}]})
    found = _probe_one(preset, opener=opener)
    assert found is not None
    assert found.protocol == "ollama"
    assert found.models == ("qwen3:4b",)
    assert opener.requests[0][0].endswith("/api/tags")


def test_non_loopback_presets_are_never_probed():
    preset = LocalEnginePreset(
        "unsafe",
        "Unsafe",
        "http://192.168.1.9:8000/v1",
    )

    class ExplodingOpener:
        def open(self, *args, **kwargs):
            raise AssertionError("non-loopback endpoint must not be touched")

    assert _probe_one(preset, opener=ExplodingOpener()) is None


def test_shared_port_preserves_engine_ambiguity():
    preset = LocalEnginePreset(
        "openai_compat_8080",
        "OpenAI-compatible endpoint :8080",
        "http://127.0.0.1:8080/v1",
        aliases=("llama.cpp", "LocalAI", "TGI"),
        identity_strength="protocol_only",
    )
    found = _probe_one(preset, opener=_Opener({"data": [{"id": "model"}]}))
    assert found is not None
    assert found.identity_strength == "protocol_only"
    assert found.engine_id == "openai_compat_8080"
    assert "llama.cpp" in found.aliases
    assert found.display_name != "llama.cpp"


def test_discovery_status_never_implies_execution_authority():
    assert discovery_status([])["execution_authorized"] is False
