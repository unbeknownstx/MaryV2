from __future__ import annotations

from mary.core.config import Config
from mary.llm.router import LLMRouter
from mary.mind.local_models import CANDIDATES


def test_local_model_catalog_has_small_current_hardware_candidates():
    by_name = {item.model: item for item in CANDIDATES}
    assert by_name["qwen3:1.7b"].approx_size_gb <= 1.5
    assert by_name["gemma3:1b"].approx_size_gb < 1.0
    assert by_name["nomic-embed-text"].role == "embeddings"
    assert "qwen3:4b" in by_name


def test_fast_ollama_purpose_can_use_separate_conversation_model(monkeypatch):
    monkeypatch.setenv("MARY_OLLAMA_MODEL", "qwen3:4b")
    monkeypatch.setenv("MARY_OLLAMA_CONVERSATION_MODEL", "qwen3:1.7b")
    router = LLMRouter(Config())
    fast = router._get_provider_for_purpose("ollama", "conversation_fast")
    normal = router.get_provider("ollama")
    assert fast.model_name() == "qwen3:1.7b"
    assert normal.model_name() == "qwen3:4b"
