from mary.realtime import RealtimeDataPlane, RealtimeDatum


def test_data_plane_is_bounded_and_sanitized():
    plane = RealtimeDataPlane(capacity=32)
    for i in range(50):
        plane.publish(
            RealtimeDatum(
                kind="audio_activity",
                source="mic",
                summary=f"chunk {i}",
                metadata={"token": "secret", "rms": i},
            )
        )
    status = plane.snapshot()
    assert status["buffered"] == 32
    assert "secret" not in repr(status)
