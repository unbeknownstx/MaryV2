from __future__ import annotations

from mary.distributed.specialist_catalog import CATALOG, specialist_status


def test_research_specialists_are_optional_and_non_authoritative(monkeypatch) -> None:
    for name in (
        "MARY_FLUID_AUDIO_ENDPOINT",
        "MARY_QWEN_ASR_ENDPOINT",
        "MARY_CHATTERBOX_ENDPOINT",
        "MARY_LLAMA_CPP_VLM_URL",
        "MARY_OMNIPARSER_ENDPOINT",
    ):
        monkeypatch.delenv(name, raising=False)
    status = specialist_status()
    ids = {item["backend_id"] for item in status["backends"]}
    assert {"fluid_audio", "qwen3_asr", "chatterbox", "llama_cpp_mtmd", "omniparser", "dspy_gepa", "graphiti"} <= ids
    assert status["semantics"]["core_startup_dependency"] is False
    assert status["semantics"]["external_identity_authority"] is False
    assert status["semantics"]["external_memory_authority"] is False
    assert status["semantics"]["arbitrary_shell"] is False


def test_catalog_declares_explicit_authority_for_every_backend() -> None:
    assert CATALOG
    assert all(item.authority for item in CATALOG)
    assert all(item.integration for item in CATALOG)
