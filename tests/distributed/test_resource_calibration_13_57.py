import pytest

from mary.distributed.resource_calibration import measure_provider_fit
from mary.distributed.resource_probe import GPUObservation, LiveResourceObservation
from scripts.calibrate_model_fit import _env_name, _provider


class _Provider:
    base_url = "http://localhost:11434"
    num_ctx = 8192

    def provider_name(self):
        return "ollama"

    def model_name(self):
        return "qwen3:1.7b"


def _discrete(free: float) -> LiveResourceObservation:
    return LiveResourceObservation(
        platform="windows",
        ram_total_gib=32.0,
        ram_free_gib=20.0,
        gpus=(
            GPUObservation(
                label="test-gpu",
                total_gib=16.0,
                free_gib=free,
                backend="cuda",
                source="nvidia_smi",
            ),
        ),
        apple_unified_memory=False,
    )


def _sequence(values):
    iterator = iter(values)
    return lambda *_args, **_kwargs: next(iterator)


def test_conversation_measurement_emits_only_conversation_role_suggestion():
    _result, measurement = measure_provider_fit(
        _Provider(),
        lambda: None,
        role="conversation",
        observer=_sequence((_discrete(12.0), _discrete(8.0))),
        residency_probe=_sequence(("not_loaded", "loaded")),
    )

    assert measurement["revision"] == "13.57"
    assert measurement["role"] == "conversation"
    assert measurement["suggested_accelerator_gib"] == 4.5
    assert measurement["suggested_accelerator_gib_conversation"] == 4.5
    assert "suggested_accelerator_gib_general" not in measurement
    assert measurement["recommendation_supported_by_measurement"] is True
    assert "conversation model" in measurement["suggestion_scope"]


def test_fast_and_utility_roles_get_matching_dynamic_keys():
    for role in ("fast", "utility"):
        _result, measurement = measure_provider_fit(
            _Provider(),
            lambda: None,
            role=role,
            observer=_sequence((_discrete(12.0), _discrete(10.0))),
            residency_probe=_sequence(("not_loaded", "loaded")),
        )
        assert measurement["role"] == role
        assert measurement[f"suggested_accelerator_gib_{role}"] == 2.5
        assert measurement["suggested_accelerator_gib"] == 2.5


def test_invalid_role_fails_before_benchmark_operation_runs():
    called = {"value": False}

    def operation():
        called["value"] = True

    with pytest.raises(ValueError, match="role must be"):
        measure_provider_fit(_Provider(), operation, role="streaming")
    assert called["value"] is False


def test_role_specific_environment_names_are_fixed_and_bounded():
    assert _env_name("ollama", "general") == "MARY_OLLAMA_RESOURCE_ACCELERATOR_GIB_GENERAL"
    assert _env_name("ollama", "conversation") == "MARY_OLLAMA_RESOURCE_ACCELERATOR_GIB_CONVERSATION"
    assert _env_name("ollama", "fast") == "MARY_OLLAMA_RESOURCE_ACCELERATOR_GIB_FAST"
    assert _env_name("ollama", "utility") == "MARY_OLLAMA_RESOURCE_ACCELERATOR_GIB_UTILITY"
    assert _env_name("llama_cpp", "fast") == "MARY_LLAMA_CPP_RESOURCE_ACCELERATOR_GIB_FAST"


def test_ollama_calibration_provider_uses_real_device_role_mapping(monkeypatch):
    monkeypatch.setenv("MARY_OLLAMA_MODEL", "qwen3:4b")
    monkeypatch.setenv("MARY_OLLAMA_CONVERSATION_MODEL", "qwen3:1.7b")
    monkeypatch.setenv("MARY_OLLAMA_UTILITY_MODEL", "gemma3:1b")

    assert _provider("ollama", "general").model_name() == "qwen3:4b"
    assert _provider("ollama", "conversation").model_name() == "qwen3:1.7b"
    assert _provider("ollama", "fast").model_name() == "qwen3:1.7b"
    assert _provider("ollama", "utility").model_name() == "gemma3:1b"


def test_role_measurement_still_refuses_recommendation_when_model_is_resident():
    _result, measurement = measure_provider_fit(
        _Provider(),
        lambda: None,
        role="utility",
        observer=_sequence((_discrete(12.0), _discrete(8.0))),
        residency_probe=_sequence(("loaded", "loaded")),
    )

    assert measurement["role"] == "utility"
    assert measurement["suggested_accelerator_gib"] is None
    assert measurement["suggested_accelerator_gib_utility"] is None
    assert measurement["fit_hint_status"] == "model_already_resident"
    assert measurement["recommendation_supported_by_measurement"] is False
