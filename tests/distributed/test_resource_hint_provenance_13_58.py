from mary.distributed.resource_hint_provenance import (
    calibration_fingerprint,
    provenance_env_name,
)
from mary.distributed.resource_requirements import explicit_resource_hints


def test_fingerprint_is_stable_and_scoped_to_model_context_role_runtime():
    base = calibration_fingerprint(runtime="ollama", role="conversation", model="qwen3:1.7b", num_ctx=8192)
    assert base == calibration_fingerprint(runtime="ollama", role="conversation", model="qwen3:1.7b", num_ctx=8192)
    assert base != calibration_fingerprint(runtime="ollama", role="conversation", model="qwen3:4b", num_ctx=8192)
    assert base != calibration_fingerprint(runtime="ollama", role="conversation", model="qwen3:1.7b", num_ctx=4096)
    assert base != calibration_fingerprint(runtime="ollama", role="utility", model="qwen3:1.7b", num_ctx=8192)


def test_legacy_explicit_hint_without_provenance_remains_compatible(monkeypatch):
    monkeypatch.setenv("MARY_OLLAMA_RESOURCE_ACCELERATOR_GIB_CONVERSATION", "3.5")
    monkeypatch.delenv("MARY_OLLAMA_RESOURCE_ACCELERATOR_GIB_CONVERSATION_PROVENANCE", raising=False)
    assert explicit_resource_hints("llm.ollama")["resource_accelerator_gib_conversation"] == 3.5


def test_matching_provenance_keeps_role_hint(monkeypatch):
    monkeypatch.setenv("MARY_OLLAMA_MODEL", "qwen3:4b")
    monkeypatch.setenv("MARY_OLLAMA_CONVERSATION_MODEL", "qwen3:1.7b")
    monkeypatch.setenv("MARY_OLLAMA_RESOURCE_ACCELERATOR_GIB_CONVERSATION", "3.5")

    from mary.llm.providers.ollama import OllamaProvider
    provider = OllamaProvider(model="qwen3:1.7b")
    token = calibration_fingerprint(
        runtime="ollama", role="conversation", model=provider.model_name(), num_ctx=provider.num_ctx
    )
    monkeypatch.setenv(provenance_env_name("ollama", "conversation"), token)
    assert explicit_resource_hints("llm.ollama")["resource_accelerator_gib_conversation"] == 3.5


def test_model_change_suppresses_only_stale_role_hint(monkeypatch):
    monkeypatch.setenv("MARY_OLLAMA_MODEL", "qwen3:4b")
    monkeypatch.setenv("MARY_OLLAMA_CONVERSATION_MODEL", "qwen3:1.7b")
    monkeypatch.setenv("MARY_OLLAMA_RESOURCE_ACCELERATOR_GIB_CONVERSATION", "3.5")
    monkeypatch.setenv("MARY_OLLAMA_RESOURCE_ACCELERATOR_GIB_UTILITY", "1.5")

    from mary.llm.providers.ollama import OllamaProvider
    provider = OllamaProvider(model="qwen3:1.7b")
    old = calibration_fingerprint(
        runtime="ollama", role="conversation", model=provider.model_name(), num_ctx=provider.num_ctx
    )
    monkeypatch.setenv(provenance_env_name("ollama", "conversation"), old)
    monkeypatch.setenv("MARY_OLLAMA_CONVERSATION_MODEL", "qwen3:4b")

    hints = explicit_resource_hints("llm.ollama")
    assert "resource_accelerator_gib_conversation" not in hints
    assert hints["resource_accelerator_gib_utility"] == 1.5


def test_malformed_provenance_fails_closed_for_that_role(monkeypatch):
    monkeypatch.setenv("MARY_OLLAMA_RESOURCE_ACCELERATOR_GIB_FAST", "2.0")
    monkeypatch.setenv(provenance_env_name("ollama", "fast"), "not-a-valid-current-token")
    assert "resource_accelerator_gib_fast" not in explicit_resource_hints("llm.ollama")
