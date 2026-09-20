from mary.perception.media_timeline import (
    MediaObservation,
    build_media_observation_timeline,
    context_window,
)


def test_media_timeline_is_sorted_bounded_derived_evidence():
    timeline = build_media_observation_timeline(
        "asset-1",
        [
            MediaObservation(4, "vision", "Mary enters frame", "vision:model"),
            MediaObservation(2, "speech", "hello", "stt:model"),
        ],
    )
    assert [x.at_seconds for x in timeline.observations] == [2.0, 4.0]
    assert timeline.authority == "derived_perception_evidence"
    assert timeline.persistence.startswith("ephemeral")


def test_context_window_interleaves_modalities_without_promoting_truth():
    timeline = build_media_observation_timeline(
        "asset-1",
        [
            MediaObservation(1, "speech", "a", "stt"),
            MediaObservation(8, "vision", "b", "vision"),
            MediaObservation(30, "vision", "c", "vision"),
        ],
    )
    window = context_window(timeline, at_seconds=9, backward_seconds=8, forward_seconds=1)
    assert [item["text"] for item in window] == ["a", "b"]
