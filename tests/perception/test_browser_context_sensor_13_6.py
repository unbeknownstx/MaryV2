from mary.perception import (
    BrowserContext,
    BrowserContextSensor,
    PerceptionDirector,
)
from mary.realtime import AttentionBus


def test_browser_context_enters_existing_perception_boundary_and_strips_url_details():
    attention = AttentionBus()
    director = PerceptionDirector(attention)
    sensor = BrowserContextSensor(director)
    observation = sensor.ingest(BrowserContext(
        page_title="Example video",
        url="https://user:password@example.com/watch?v=secret",
        video_subtitle_segment="The speaker mentions Mary.",
        media_state="playing",
    ))
    assert observation.modality == "screen"
    assert observation.metadata["url_domain"] == "example.com"
    assert "password" not in str(observation.to_dict())
    assert observation.to_dict()["authority"] == "environment_context_only"
    assert attention.snapshot()["published"] >= 1
