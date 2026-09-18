from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]


def _text(path: str) -> str:
    return (ROOT / path).read_text(encoding="utf-8")


def test_native_creator_lab_routes_picked_image_through_bounded_vision_capability():
    app = _text("ios/MaryV2iOS/Sources/AppState.swift")
    view = _text("ios/MaryV2iOS/Sources/CreatorLabView.swift")
    client = _text("ios/MaryV2iOS/Sources/MaryCoreClient.swift")

    assert 'import CryptoKit' in app
    assert 'perception.asset.register' in app
    assert 'sensor.image_describe' in app
    assert 'image.base64EncodedString()' in app
    assert 'capabilityTaskStatus(taskID)' in app
    assert 'Let Mary look at the image' in view
    assert 'Raw pixels are ephemeral task input' in view
    assert 'dispatchCapability' in client


def test_creator_lab_no_longer_claims_core_image_transport_is_missing():
    view = _text("ios/MaryV2iOS/Sources/CreatorLabView.swift")
    assert "until Core vision upload is live" not in view
    assert "next transport step" not in view
