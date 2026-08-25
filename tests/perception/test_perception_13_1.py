from mary.perception import PerceptionDirector
from mary.realtime import AttentionBus


def test_perception_describes_without_durable_authority_or_raw_media():
    bus = AttentionBus()
    director = PerceptionDirector(bus)
    obs = director.observe(
        "A code editor is open with a Python file.",
        modality="screen",
        confidence=0.9,
        importance=0.8,
        metadata={"screenshot": "raw", "base64": "raw", "window": "VS Code"},
    )
    payload = obs.to_dict()
    assert payload["authority"] == "environment_context_only"
    assert payload["durable"] is False
    assert "screenshot" not in payload["metadata"]
    assert "base64" not in payload["metadata"]
    pending = bus.pending()
    assert pending and pending[0].source.value == "visual"
