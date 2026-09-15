from __future__ import annotations

from types import SimpleNamespace

import pytest

from mary.core.config import LLMConfig
from mary.desktop import runtime_supervisor
from mary.desktop import device_node as desktop_device_node
from mary.distributed.permissions import DeviceExecutionPermissions
from mary.distributed.tasks import _sanitize_task_args
from mary.llm.providers import local_runtime as local_runtime_module
from mary.llm.providers.device_local import DeviceLocalProvider
from mary.llm.providers.local_runtime import LocalRuntimeProvider


def test_default_conversation_prefers_local_device_but_tasks_remain_cloud_first():
    config = LLMConfig()
    assert config.conversation_provider_order[0] == "local_device"
    assert config.free_provider_order[0] == "groq"


def test_lm_studio_role_is_selected_when_loaded(monkeypatch):
    monkeypatch.setenv("MARY_LOCAL_INFERENCE_RUNTIME", "lm_studio")
    monkeypatch.setenv("MARY_LM_STUDIO_MODEL", "mary-conversation")
    monkeypatch.setenv("MARY_LM_STUDIO_BASE_URL", "http://127.0.0.1:1234/v1")
    monkeypatch.setattr(
        local_runtime_module,
        "_openai_models",
        lambda _base_url, timeout=0.45: ("mary-conversation",),
    )

    provider = LocalRuntimeProvider(role="conversation")
    status = provider.runtime_status()

    assert status["available"] is True
    assert status["runtime"] == "lm_studio"
    assert status["model"] == "mary-conversation"
    assert provider.provider_name() == "local_device"


def test_fast_local_role_prefers_small_worker_runtime_without_changing_normal_order(monkeypatch):
    monkeypatch.setenv("MARY_LOCAL_INFERENCE_RUNTIME", "auto")
    monkeypatch.setenv(
        "MARY_LOCAL_FAST_RUNTIME_ORDER",
        "ollama,lm_studio,llama_cpp",
    )

    fast = LocalRuntimeProvider(role="fast")
    conversation = LocalRuntimeProvider(role="conversation")

    assert fast._runtime_order()[0] == "ollama"
    assert conversation._runtime_order()[0] == "lm_studio"


def test_fast_ollama_role_supports_explicit_small_model(monkeypatch):
    monkeypatch.setenv("MARY_OLLAMA_MODEL", "qwen3:4b")
    monkeypatch.setenv("MARY_OLLAMA_CONVERSATION_MODEL", "qwen3:4b")
    monkeypatch.setenv("MARY_OLLAMA_FAST_MODEL", "qwen3:1.7b")

    assert local_runtime_module._ollama_model_for_role("conversation") == "qwen3:4b"
    assert local_runtime_module._ollama_model_for_role("fast") == "qwen3:1.7b"


def test_desktop_node_fast_role_can_reuse_configured_utility_model(monkeypatch):
    monkeypatch.setenv("MARY_OLLAMA_MODEL", "qwen3:4b")
    monkeypatch.setenv("MARY_OLLAMA_CONVERSATION_MODEL", "qwen3:4b")
    monkeypatch.delenv("MARY_OLLAMA_FAST_MODEL", raising=False)
    monkeypatch.setenv("MARY_OLLAMA_UTILITY_MODEL", "qwen3:1.7b")

    assert desktop_device_node._ollama_model_for_role("conversation") == "qwen3:4b"
    assert desktop_device_node._ollama_model_for_role("fast") == "qwen3:1.7b"


def test_llm_local_task_uses_same_bounded_message_contract():
    payload = _sanitize_task_args(
        "llm.local",
        {
            "messages": [
                {"role": "system", "content": "You are Mary."},
                {"role": "user", "content": "Hey."},
            ],
            "role": "conversation",
            "temperature": 0.8,
            "max_tokens": 256,
        },
    )
    assert payload["role"] == "conversation"
    assert payload["max_tokens"] == 256
    assert len(payload["messages"]) == 2


def test_llm_local_remains_device_permission_gated(tmp_path):
    permissions = DeviceExecutionPermissions(tmp_path / "permissions.json")
    assert permissions.is_allowed("llm.local") is False
    permissions.allow("llm.local")
    assert permissions.is_allowed("llm.local") is True


def test_device_local_provider_maps_conversation_purpose_without_model_authority():
    provider = DeviceLocalProvider(
        registry=SimpleNamespace(),
        broker=SimpleNamespace(),
        role="general",
        timeout_seconds=10,
    )
    assert provider.for_purpose("conversation").role == "conversation"
    assert provider.for_purpose("conversation_fast").role == "fast"
    assert provider.for_purpose("task_generation").role == "general"


def test_runtime_supervisor_subprocess_uses_utf8_replacement_decoding(monkeypatch):
    captured = {}

    def fake_run(command, **kwargs):
        captured["command"] = list(command)
        captured["kwargs"] = dict(kwargs)
        return SimpleNamespace(returncode=0, stdout="", stderr="")

    monkeypatch.setattr(runtime_supervisor.subprocess, "run", fake_run)

    runtime_supervisor._run(["lms", "status"], timeout=1.0)

    assert captured["kwargs"]["text"] is True
    assert captured["kwargs"]["encoding"] == "utf-8"
    assert captured["kwargs"]["errors"] == "replace"


def test_runtime_supervisor_recognizes_downloaded_and_loaded_lm_studio_rows():
    library = [
        {
            "modelKey": "qwen/qwen3-4b-2507",
            "indexedModelIdentifier": "qwen/qwen3-4b-2507",
        }
    ]
    loaded = [
        {
            "identifier": "mary-conversation",
            "status": "idle",
        }
    ]
    assert runtime_supervisor._model_is_downloaded(
        library,
        "qwen/qwen3-4b-2507",
    )
    assert runtime_supervisor._identifier_is_loaded(
        loaded,
        "mary-conversation",
    )


class _FailingService:
    def synthesize(self, *_args, **_kwargs):
        raise RuntimeError("primary voice failed")


class _FallbackVoice:
    status = SimpleNamespace(enabled=True, provider="windows_sapi")

    def synthesize(self, text, **_kwargs):
        return {
            "status": "success",
            "provider": "windows_sapi",
            "spoken_text": text,
            "audio_base64": "AA==",
        }


def test_auto_fast_voice_can_fall_back_after_runtime_cloud_failure():
    from mary.desktop.voice import DesktopVoiceEngine, DesktopVoiceStatus

    voice = DesktopVoiceEngine(
        service=_FailingService(),
        status=DesktopVoiceStatus(
            enabled=True,
            provider="elevenlabs",
            premium=True,
        ),
        failure_fallback=_FallbackVoice(),
    )
    result = voice.synthesize("Hey Melvin.")
    assert result["status"] == "success"
    assert result["provider"] == "windows_sapi"
    assert result["fallback_from"] == "elevenlabs"
    assert "RuntimeError" in result["primary_error"]
