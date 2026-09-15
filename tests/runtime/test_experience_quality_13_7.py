from mary.runtime.experience_quality import ExperienceQualityMonitor


def test_experience_classes_text_and_voice_without_character_authority():
    monitor = ExperienceQualityMonitor()
    assert monitor.classify(500, channel="text") == "instant"
    assert monitor.classify(2200, channel="text") == "responsive"
    assert monitor.classify(7000, channel="text") == "delayed"
    assert monitor.classify(12000, channel="text") == "degraded"
    assert monitor.classify(1500, channel="voice") == "instant"
    assert monitor.classify(3000, channel="voice") == "responsive"


def test_experience_monitor_is_bounded_content_free_operational_state():
    monitor = ExperienceQualityMonitor(capacity=16)
    for index in range(30):
        monitor.observe_turn(600 + index, outcome="success")
    monitor.observe_turn(12000, voice_input=True, outcome="success")
    monitor.note_degraded("renderer:fallback")
    snapshot = monitor.snapshot()
    assert snapshot["sample_count"] == 16
    assert snapshot["latest_class"] == "degraded"
    assert 0.0 <= snapshot["success_rate"] <= 1.0
    assert "renderer:fallback" in snapshot["recent_degraded_reasons"]
    semantics = snapshot["semantics"].lower()
    assert "identity" in semantics and "memory" in semantics
    assert "prompt" not in str(snapshot).lower()
