import pytest

from mary.perception.assets import PerceptionAssetRegistry, sha256_bytes


def test_asset_registry_never_stores_raw_media():
    registry = PerceptionAssetRegistry(capacity=8)
    raw = b"fake-image-bytes"
    item = registry.register(
        kind="image",
        source="iphone_creator_lab",
        mime_type="image/jpeg",
        content_sha256=sha256_bytes(raw),
        byte_count=len(raw),
    )
    assert "bytes" not in item
    assert "data" not in item
    assert registry.status()["raw_media_stored"] is False


def test_asset_becomes_seen_only_after_grounded_description():
    registry = PerceptionAssetRegistry()
    item = registry.register(kind="image", source="desktop")
    assert item["description_source"] == "unseen_asset"
    grounded = registry.describe(
        item["asset_id"],
        description="A code editor shows Mary's desktop UI and a visible status panel.",
        provider="local_vlm",
        model="test-vlm",
    )
    assert grounded["description_source"] == "perception_capability"
    assert "code editor" in grounded["description"]


def test_unknown_asset_cannot_receive_fabricated_grounding():
    registry = PerceptionAssetRegistry()
    with pytest.raises(ValueError, match="Unknown perception asset"):
        registry.describe("asset_missing", description="something")


def test_registry_is_bounded():
    registry = PerceptionAssetRegistry(capacity=8)
    first = registry.register(kind="image", source="test")["asset_id"]
    for _ in range(10):
        registry.register(kind="image", source="test")
    with pytest.raises(ValueError):
        registry.get(first)
    assert registry.status()["count"] == 8
