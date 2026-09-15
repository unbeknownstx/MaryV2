from __future__ import annotations

import base64

import pytest

from mary.distributed import CapabilityDescriptor, NodeDescriptor, NodeRegistry
from mary.distributed.permissions import DeviceExecutionPermissions
from mary.distributed.sensors import (
    AUDIO_TRANSCRIBE_CAPABILITY,
    SCREEN_CAPTURE_CAPABILITY,
    sanitize_sensor_result,
    sanitize_sensor_task_args,
)
from mary.distributed.tasks import DeviceTaskBroker


def test_audio_task_is_bounded_and_round_trips_base64():
    raw = b"RIFF" + b"0" * 128
    payload = sanitize_sensor_task_args(
        AUDIO_TRANSCRIBE_CAPABILITY,
        {"audio_base64": base64.b64encode(raw).decode("ascii"), "suffix": ".wav", "language": "en"},
    )
    assert base64.b64decode(payload["audio_base64"]) == raw
    assert payload["suffix"] == ".wav"
    assert payload["language"] == "en"


def test_audio_task_rejects_invalid_or_unbounded_input():
    with pytest.raises(ValueError):
        sanitize_sensor_task_args(AUDIO_TRANSCRIBE_CAPABILITY, {"audio_base64": "not-base64", "suffix": ".wav"})
    with pytest.raises(ValueError):
        sanitize_sensor_task_args(
            AUDIO_TRANSCRIBE_CAPABILITY,
            {"audio_base64": base64.b64encode(b"x" * (4 * 1024 * 1024 + 1)).decode("ascii"), "suffix": ".wav"},
        )


def test_screen_capture_request_is_narrow_and_clamped():
    payload = sanitize_sensor_task_args(
        SCREEN_CAPTURE_CAPABILITY,
        {"max_width": 9000, "quality": 100, "all_screens": True, "path": "/secret"},
    )
    assert payload == {"max_width": 1920, "quality": 90, "all_screens": True}


def test_screen_result_is_ephemeral_evidence_with_digest():
    image = b"jpeg-test-bytes"
    payload = sanitize_sensor_result(
        SCREEN_CAPTURE_CAPABILITY,
        {"image_base64": base64.b64encode(image).decode("ascii"), "width": 800, "height": 450},
    )
    assert base64.b64decode(payload["image_base64"]) == image
    assert payload["mime_type"] == "image/jpeg"
    assert len(payload["sha256"]) == 64
    assert "memory" in payload["privacy"]


def test_sensor_capabilities_are_local_opt_in_permissions(tmp_path):
    permissions = DeviceExecutionPermissions(tmp_path / "permissions.json")
    assert not permissions.is_allowed(AUDIO_TRANSCRIBE_CAPABILITY)
    assert not permissions.is_allowed(SCREEN_CAPTURE_CAPABILITY)
    permissions.allow(AUDIO_TRANSCRIBE_CAPABILITY)
    permissions.allow(SCREEN_CAPTURE_CAPABILITY)
    assert permissions.is_allowed(AUDIO_TRANSCRIBE_CAPABILITY)
    assert permissions.is_allowed(SCREEN_CAPTURE_CAPABILITY)


def test_broker_routes_only_to_advertised_sensor_node():
    registry = NodeRegistry()
    registry.register(NodeDescriptor(
        node_id="mac-sensor",
        role="capability_node",
        host_type="capability_node",
        platform="macos",
        capabilities={AUDIO_TRANSCRIBE_CAPABILITY: CapabilityDescriptor(AUDIO_TRANSCRIBE_CAPABILITY, private=True, local=True)},
    ))
    broker = DeviceTaskBroker(lifecycle_lock=registry.lifecycle_lock, live_node=registry.is_live)
    raw = base64.b64encode(b"RIFFaudio").decode("ascii")
    task = broker.enqueue(
        registry,
        capability=AUDIO_TRANSCRIBE_CAPABILITY,
        intent="transcribe creator microphone utterance",
        args={"audio_base64": raw, "suffix": ".wav", "language": "en"},
        requester_device_id="stream-host",
    )
    assert task.selected_node_id == "mac-sensor"
    assert task.capability == AUDIO_TRANSCRIBE_CAPABILITY
    assert task.status == "queued"
