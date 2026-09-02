from mary.expression.delivery_plan import DeliveryPlan
from mary.expression.motion_library import MotionLibrary
from mary.expression.performance_packet import build_performance_packet


def test_performance_packet_projects_motion_cues_from_existing_delivery_authority():
    packet = build_performance_packet(
        "That is an extremely unserious argument.",
        {
            "profile": "conversational",
            "energy": .58,
            "warmth": .4,
            "pace": 1.0,
            "avatar_expression": "amused",
            "gesture_style": "teasing",
            "gaze_style": "engaged",
            "head_style": "natural",
            "interruptible": True,
        },
        social_context="private",
    )
    assert len(packet.motion_cues) == len(packet.segments) == 1
    assert packet.motion_cues[0].motion_id in {"shrug_dry", "teasing_point", "laugh_small", "talk_neutral"}
    payload = packet.to_dict()
    assert payload["motion_cues"][0]["motion_id"]
    assert "identity" in MotionLibrary().snapshot()["policy"].lower()
