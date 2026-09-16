from mary.creative.creator_lab import build_creator_packet, effective_asset_description


def test_creator_lab_requires_grounding_before_mary_comments_on_unseen_image():
    packet = build_creator_packet(
        asset={"kind": "image", "uri": "asset://mary/generated-1.png"},
        intent="Mary reacts to this picture in her own voice.",
    )
    assert packet["ready_for_mary_authoring"] is False
    assert packet["jobs"][0]["kind"] == "vision.describe"
    assert packet["execution_authorized"] is False
    assert packet["identity_owner"] is False


def test_creator_description_can_ground_caption_voice_and_video_plan():
    packet = build_creator_packet(
        asset={
            "kind": "image",
            "uri": "asset://mary/generated-2.png",
            "creator_description": "Mary stands under neon lights in a rainy city street.",
        },
        intent="Make a dry joke about pretending this was a casual walk.",
        outputs=["mary_caption", "mary_voice", "video_brief"],
        tone="dry, warm",
    )
    assert packet["ready_for_mary_authoring"] is True
    assert packet["description_source"] == "creator_description"
    kinds = [row["kind"] for row in packet["jobs"]]
    assert kinds == ["mary.author", "voice.synthesize", "video.render"]
    assert packet["jobs"][-1]["requires_approval"] is True


def test_perception_description_has_priority_over_creator_description():
    description, source = effective_asset_description({
        "creator_description": "a red room",
        "perception_description": "Mary in a purple beanie beside a rainy window",
    })
    assert description == "Mary in a purple beanie beside a rainy window"
    assert source == "perception_capability"


def test_image_variant_is_planned_but_never_silently_executed():
    packet = build_creator_packet(
        asset={"creator_description": "Mary portrait"},
        outputs=["image_variant"],
    )
    assert packet["jobs"][0]["kind"] == "image.generate"
    assert packet["jobs"][0]["requires_approval"] is True
    assert packet["publishing_authorized"] is False
