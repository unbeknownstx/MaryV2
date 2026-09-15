import json

from mary.distributed.resource_calibration import measure_provider_fit, ollama_residency
from mary.distributed.resource_probe import GPUObservation, LiveResourceObservation


class _Provider:
    base_url = "http://localhost:11434"
    num_ctx = 8192

    def provider_name(self):
        return "ollama"

    def model_name(self):
        return "qwen3:4b"


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


def _unified(free: float) -> LiveResourceObservation:
    return LiveResourceObservation(
        platform="darwin",
        ram_total_gib=16.0,
        ram_free_gib=free,
        gpus=(),
        apple_unified_memory=True,
    )


def _sequence(values):
    iterator = iter(values)
    return lambda *_args, **_kwargs: next(iterator)


def test_proven_cold_load_produces_measurement_supported_general_recommendation():
    result, measurement = measure_provider_fit(
        _Provider(),
        lambda: {"benchmark": "sanitized"},
        observer=_sequence((_discrete(12.0), _discrete(8.0))),
        residency_probe=_sequence(("not_loaded", "loaded")),
    )

    assert result == {"benchmark": "sanitized"}
    assert measurement["accelerator_observed_delta_gib"] == 4.0
    assert measurement["suggested_accelerator_gib_general"] == 4.5
    assert measurement["recommendation_supported_by_measurement"] is True
    assert measurement["fit_hint_status"] == "cold_load_measured"
    assert measurement["model"] == "qwen3:4b"
    assert measurement["num_ctx"] == 8192
    assert measurement["content_retained"] is False


def test_already_resident_model_never_produces_recommendation_even_with_delta():
    _result, measurement = measure_provider_fit(
        _Provider(),
        lambda: None,
        observer=_sequence((_discrete(12.0), _discrete(7.0))),
        residency_probe=_sequence(("loaded", "loaded")),
    )

    assert measurement["accelerator_observed_delta_gib"] == 5.0
    assert measurement["suggested_accelerator_gib_general"] is None
    assert measurement["recommendation_supported_by_measurement"] is False
    assert measurement["fit_hint_status"] == "model_already_resident"


def test_unknown_residency_never_produces_recommendation():
    _result, measurement = measure_provider_fit(
        _Provider(),
        lambda: None,
        observer=_sequence((_discrete(12.0), _discrete(8.0))),
        residency_probe=_sequence(("unknown", "unknown")),
    )

    assert measurement["suggested_accelerator_gib_general"] is None
    assert measurement["recommendation_supported_by_measurement"] is False
    assert measurement["fit_hint_status"] == "residency_unverified"


def test_apple_unified_memory_uses_ram_as_accelerator_measurement():
    _result, measurement = measure_provider_fit(
        _Provider(),
        lambda: None,
        observer=_sequence((_unified(12.0), _unified(8.0))),
        residency_probe=_sequence(("not_loaded", "loaded")),
    )

    assert measurement["apple_unified_memory"] is True
    assert measurement["accelerator_source"] == "apple_unified_memory"
    assert measurement["accelerator_total_gib"] == 16.0
    assert measurement["accelerator_observed_delta_gib"] == 4.0
    assert measurement["recommendation_supported_by_measurement"] is True


def test_tiny_cold_load_delta_is_reported_but_not_recommended():
    _result, measurement = measure_provider_fit(
        _Provider(),
        lambda: None,
        observer=_sequence((_discrete(12.0), _discrete(11.95))),
        residency_probe=_sequence(("not_loaded", "loaded")),
    )

    assert measurement["accelerator_observed_delta_gib"] == 0.05
    assert measurement["suggested_accelerator_gib_general"] is None
    assert measurement["fit_hint_status"] == "cold_load_delta_too_small"


class _Response:
    def __init__(self, payload):
        self.payload = payload

    def __enter__(self):
        return self

    def __exit__(self, *_args):
        return False

    def read(self):
        return json.dumps(self.payload).encode("utf-8")


def test_ollama_residency_matches_latest_alias_and_exact_model():
    provider = _Provider()
    loaded = ollama_residency(
        provider,
        opener=lambda *_args, **_kwargs: _Response({"models": [{"name": "qwen3:4b"}]}),
    )
    missing = ollama_residency(
        provider,
        opener=lambda *_args, **_kwargs: _Response({"models": [{"name": "other:latest"}]}),
    )

    assert loaded == "loaded"
    assert missing == "not_loaded"


def test_non_ollama_provider_residency_is_unknown_without_network_call():
    class OtherProvider(_Provider):
        def provider_name(self):
            return "llama_cpp"

    called = {"value": False}

    def opener(*_args, **_kwargs):
        called["value"] = True
        raise AssertionError("should not be called")

    assert ollama_residency(OtherProvider(), opener=opener) == "unknown"
    assert called["value"] is False


def test_measurement_contains_no_operation_result_or_prompt_content():
    private_value = "PRIVATE-CALIBRATION-CONTENT"
    result, measurement = measure_provider_fit(
        _Provider(),
        lambda: {"raw": private_value},
        observer=_sequence((_discrete(12.0), _discrete(8.0))),
        residency_probe=_sequence(("not_loaded", "loaded")),
    )

    assert result["raw"] == private_value
    serialized = json.dumps(measurement, sort_keys=True)
    assert private_value not in serialized
    assert "prompt" not in serialized.lower()
    assert measurement["authority"] == "operational_measurement_only"
