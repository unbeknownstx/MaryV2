from __future__ import annotations

from mary.expression.performance_packet import build_performance_packet
from mary.expression.surface_performance import (
    capabilities_for_surface,
    normalize_surface,
    project_performance_packet,
)


def test_surface_aliases_resolve_to_one_truthful_profile():
    assert normalize_surface("mac_desktop") == "desktop"
    assert normalize_surface("pwa") == "mobile_web"
    assert normalize_surface("iphone") == "ios_native"
    assert normalize_surface("unknown_future_body") == "generic"


def test_desktop_projects_existing_performance_without_becoming_authority():
    packet = build_performance_packet(
        "Seriously? Fine, show me.",
        {
            "profile": "teasing",
            "avatar_expression": "happy",
            "gesture_style": "tease",
            "gaze_style": "direct",
            "head_style": "tilt",
            "energy": 0.62,
        },
    ).to_dict()

    projected = project_performance_packet(packet, surface="desktop")

    assert projected["identity_owner"] == "mary_core"
    assert projected["authority"] == "surface_presentation_only"
    assert projected["persistence"] == "none"
    assert projected["surface"] == "desktop"
    assert "expression_cues" in projected["supported_channels"]
    assert "gaze_cues" in projected["supported_channels"]
    assert "semantic_motion" in projected["supported_channels"]
    assert projected["capabilities"]["lip_sync"] is True
    assert projected["capabilities"]["motion_assets"] is False
    assert packet["text"] == "Seriously? Fine, show me."


def test_ios_degrades_body_motion_but_keeps_direction_and_voice():
    packet = build_performance_packet(
        "Okay, that's actually kind of cute.",
        {
            "avatar_expression": "happy",
            "gesture_style": "amused",
            "gaze_style": "soft",
            "head_style": "tilt",
            "energy": 0.45,
        },
    ).to_dict()

    projected = project_performance_packet(packet, surface="ios_native")

    assert "expression_cues" in projected["supported_channels"]
    assert "gaze_cues" in projected["supported_channels"]
    assert "head_motion" in projected["supported_channels"]
    assert "voice_direction" in projected["supported_channels"]
    assert "semantic_motion" in projected["degraded_channels"]
    assert projected["fallbacks"]["semantic_motion"] == "retain expression/voice without body motion"


def test_capability_override_is_bounded_to_known_fields():
    capabilities = capabilities_for_surface(
        "vr",
        {
            "vr": True,
            "locomotion": True,
            "motion_assets": True,
            "identity_owner": True,
        },
    )
    payload = capabilities.to_dict()

    assert payload["vr"] is True
    assert payload["locomotion"] is True
    assert payload["motion_assets"] is True
    assert "identity_owner" not in payload
