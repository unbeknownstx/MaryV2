from dataclasses import dataclass

from mary.expression.social_delivery import SocialDeliveryPlanner


@dataclass
class Emotion:
    valence: float = 0.4
    arousal: float = 0.5
    intensity: float = 0.6


def test_partner_private_delivery_is_warmer_and_more_intimate_than_public():
    planner = SocialDeliveryPlanner()
    private = planner.build(relationship_mode="partner", emotional_state=Emotion(), privacy_scope="private")
    public = planner.build(relationship_mode="partner", emotional_state=Emotion(), privacy_scope="public")
    assert private.intimacy > public.intimacy
    assert private.warmth >= public.warmth
    assert private.to_dict()["authority"] == "delivery_projection_only"


def test_unknown_mode_falls_back_to_friend():
    envelope = SocialDeliveryPlanner().build(relationship_mode="unknown")
    assert envelope.relationship_mode == "friend"
    assert 0.0 <= envelope.pace <= 1.0
