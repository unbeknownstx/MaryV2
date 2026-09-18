from __future__ import annotations

import base64
import json

from mary.distributed.sensors import (
    IMAGE_DESCRIBE_CAPABILITY,
    SCREEN_DESCRIBE_CAPABILITY,
    _safe_endpoint,
    _vision_config,
    sanitize_sensor_result,
    sanitize_sensor_task_args,
)


def test_screen_describe_is_bounded_and_has_no_action_arguments() -> None:
    args = sanitize_sensor_task_args(
        SCREEN_DESCRIBE_CAPABILITY,
        {"max_width": 99999, "quality": 100, "all_screens": True, "mode": "ui", "url": "http://evil", "command": "click"},
    )
    assert args == {"max_width": 1920, "quality": 90, "all_screens": True, "mode": "ui"}
    assert "url" not in args
    assert "command" not in args


def test_visual_endpoint_policy_rejects_remote_plain_http() -> None:
    assert _safe_endpoint("http://example.com/vision") == ""
    assert _safe_endpoint("http://127.0.0.1:8080")
    assert _safe_endpoint("https://vision.example.com")


def test_visual_config_is_device_owned(monkeypatch) -> None:
    monkeypatch.setenv("MARY_VISION_PROVIDER", "llama_cpp_mtmd")
    monkeypatch.setenv("MARY_LLAMA_CPP_VLM_URL", "http://localhost:8080")
    provider, endpoint = _vision_config()
    assert provider == "llama_cpp_mtmd"
    assert endpoint == "http://localhost:8080"


def test_visual_result_is_description_only_and_sanitized() -> None:
    safe = sanitize_sensor_result(
        SCREEN_DESCRIBE_CAPABILITY,
        {
            "description": "VS Code is foreground with a failing test visible.",
            "elements": [
                {"label": "Terminal", "kind": "panel", "confidence": 1.5, "secret": "drop"},
            ],
            "provider": "omniparser",
            "model": "test",
            "source_sha256": "a" * 64,
            "token": "must-not-survive",
        },
    )
    assert safe["description"].startswith("VS Code")
    assert safe["elements"] == [{"label": "Terminal", "kind": "panel", "confidence": 1.0}]
    assert "token" not in safe
    assert "control" in safe["privacy"]



def test_image_describe_accepts_only_bounded_visual_payload_and_drops_commands() -> None:
    raw = b"tiny-image-placeholder"
    args = sanitize_sensor_task_args(
        IMAGE_DESCRIBE_CAPABILITY,
        {
            "image_base64": base64.b64encode(raw).decode("ascii"),
            "mime_type": "image/jpeg",
            "mode": "creative",
            "asset_id": "asset_test",
            "url": "http://evil",
            "command": "click",
        },
    )
    assert base64.b64decode(args["image_base64"]) == raw
    assert args["mime_type"] == "image/jpeg"
    assert args["mode"] == "creative"
    assert args["asset_id"] == "asset_test"
    assert "url" not in args
    assert "command" not in args


def test_image_describe_result_uses_same_evidence_only_boundary() -> None:
    safe = sanitize_sensor_result(
        IMAGE_DESCRIBE_CAPABILITY,
        {
            "description": "Mary stands beneath warm lanterns in a floral kimono.",
            "provider": "llama_cpp_mtmd",
            "model": "vision-test",
            "source_sha256": "b" * 64,
            "command": "post this",
        },
    )
    assert "warm lanterns" in safe["description"]
    assert safe["provider"] == "llama_cpp_mtmd"
    assert safe["source_sha256"] == "b" * 64
    assert "command" not in safe
    assert "memory truth" in safe["privacy"]
