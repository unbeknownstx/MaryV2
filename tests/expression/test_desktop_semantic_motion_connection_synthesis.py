from pathlib import Path


def test_desktop_consumes_performance_packet_motion_cues():
    source = (Path(__file__).resolve().parents[2] / "desktop" / "src" / "main.js").read_text(encoding="utf-8")
    assert "motionCueForSegment" in source
    assert "currentPerformancePacket?.motion_cues" in source
    assert "applySemanticMotionPose" in source
    assert "humanoid.setNormalizedPose" in source
    for motion_id in ("explain_small", "shrug_dry", "teasing_point", "thinking_pause"):
        assert motion_id in source
