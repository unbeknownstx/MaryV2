from __future__ import annotations

from mary.distributed.creative_runtime import (
    creative_candidates,
    creative_runtime,
    creative_runtime_catalog,
)


def test_creative_catalog_is_optional_and_bounded(monkeypatch) -> None:
    for name in (
        "MARY_DRAW_THINGS_READY",
        "MARY_LOCAL_UPSCALER_READY",
        "MARY_COMFYUI_READY",
        "MARY_CLIENT_WEBGPU_READY",
    ):
        monkeypatch.delenv(name, raising=False)
    for item in creative_runtime_catalog():
        assert item["startup_dependency"] is False
        assert item["authority"] == "creative_execution_only"
        assert item["local"] is True


def test_draw_things_exposes_useful_apple_operations() -> None:
    item = creative_runtime("draw_things")
    assert item is not None
    assert item.platform == "apple"
    assert item.supports("text_to_image")
    assert item.supports("image_to_image")
    assert item.supports("inpaint")
    assert item.supports("upscale")


def test_runtime_is_not_available_until_device_explicitly_advertises_it(monkeypatch) -> None:
    monkeypatch.delenv("MARY_DRAW_THINGS_READY", raising=False)
    monkeypatch.delenv("MARY_DRAW_THINGS_ENDPOINT", raising=False)
    assert creative_candidates("text_to_image") == []


def test_explicit_draw_things_advertisement_creates_candidate(monkeypatch) -> None:
    monkeypatch.setenv("MARY_DRAW_THINGS_READY", "1")
    candidates = creative_candidates("inpaint")
    assert any(item["name"] == "draw_things" for item in candidates)


def test_webgpu_can_be_a_client_side_capability(monkeypatch) -> None:
    monkeypatch.setenv("MARY_CLIENT_WEBGPU_READY", "true")
    candidates = creative_candidates("upscale")
    webgpu = next(item for item in candidates if item["name"] == "client_webgpu")
    assert webgpu["transport"] == "client_capability_channel"
    assert webgpu["private"] is True


def test_unknown_creative_operation_is_never_routed() -> None:
    assert creative_candidates("arbitrary_shell") == []
