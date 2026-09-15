from __future__ import annotations

from mary.distributed.local_runtime_catalog import (
    local_runtime_catalog,
    openai_compatible_runtime_provider,
    runtime_descriptor,
)


def test_catalog_contains_interchangeable_local_runtimes() -> None:
    names = {item["name"] for item in local_runtime_catalog()}
    assert {"ollama", "llama_cpp", "lm_studio", "jan", "mlx"}.issubset(names)


def test_catalog_does_not_probe_servers_or_make_them_startup_dependencies() -> None:
    for item in local_runtime_catalog():
        assert item["startup_dependency"] is False
        assert item["local"] is True
        assert item["private"] is True


def test_lm_studio_uses_expected_loopback_compatible_endpoint(monkeypatch) -> None:
    monkeypatch.delenv("MARY_LM_STUDIO_BASE_URL", raising=False)
    descriptor = runtime_descriptor("lm_studio")
    assert descriptor is not None
    assert descriptor.protocol == "openai_compatible"
    assert descriptor.base_url() == "http://127.0.0.1:1234/v1"


def test_jan_uses_expected_loopback_compatible_endpoint(monkeypatch) -> None:
    monkeypatch.delenv("MARY_JAN_BASE_URL", raising=False)
    descriptor = runtime_descriptor("jan")
    assert descriptor is not None
    assert descriptor.protocol == "openai_compatible"
    assert descriptor.base_url() == "http://127.0.0.1:1337/v1"


def test_runtime_is_not_marked_configured_just_because_default_url_exists(monkeypatch) -> None:
    monkeypatch.delenv("MARY_LM_STUDIO_BASE_URL", raising=False)
    monkeypatch.delenv("MARY_LM_STUDIO_READY", raising=False)
    descriptor = runtime_descriptor("lm_studio")
    assert descriptor is not None
    assert descriptor.configured() is False


def test_generic_openai_transport_is_reused_for_lm_studio(monkeypatch) -> None:
    monkeypatch.setenv("MARY_LM_STUDIO_MODEL", "local-test-model")
    provider = openai_compatible_runtime_provider("lm_studio")
    assert provider.provider_name() == "lm_studio"
    assert provider.model_name() == "local-test-model"
    assert provider.base_url == "http://127.0.0.1:1234/v1"
    route = provider.route_capabilities()
    assert "local_only" in route.privacy_modes
