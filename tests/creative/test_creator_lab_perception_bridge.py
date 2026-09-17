from mary.creative.creator_lab import build_creator_packet
from mary.perception.assets import PerceptionAssetRegistry


def test_grounded_perception_asset_flows_directly_into_mary_authoring():
    registry = PerceptionAssetRegistry()
    asset = registry.register(kind="image", source="iphone_creator_lab", mime_type="image/jpeg")
    asset = registry.describe(
        asset["asset_id"],
        description="Mary is standing beneath warm lanterns in a floral kimono.",
        provider="local_vlm",
        model="vision-test",
    )
    packet = build_creator_packet(
        asset=asset,
        intent="React to the picture and make a short caption.",
        outputs=["mary_caption", "mary_voice", "video_brief"],
    )
    assert packet["ready_for_mary_authoring"] is True
    assert packet["description_source"] == "perception_capability"
    assert packet["asset"]["asset_id"] == asset["asset_id"]
    assert packet["asset"]["perception_provider"] == "local_vlm"
    assert [job["kind"] for job in packet["jobs"]] == [
        "mary.author",
        "voice.synthesize",
        "video.render",
    ]


def test_unseen_registry_asset_still_requires_vision_first():
    registry = PerceptionAssetRegistry()
    asset = registry.register(kind="image", source="desktop")
    packet = build_creator_packet(asset=asset, outputs=["mary_caption"])
    assert packet["ready_for_mary_authoring"] is False
    assert packet["jobs"][0]["kind"] == "vision.describe"
