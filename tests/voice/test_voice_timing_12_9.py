from __future__ import annotations

from mary.desktop.voice import DesktopVoiceEngine


def test_disabled_voice_reports_bounded_timing_metadata() -> None:
    """12.9 must expose useful voice timing even when TTS is disabled."""

    payload = DesktopVoiceEngine().synthesize("Hey Mary")

    assert payload["status"] == "disabled"
    timings = payload["timings"]
    assert timings["speech_render_ms"] >= 0
    assert timings["tts_synthesis_ms"] == 0
    assert timings["voice_total_ms"] >= timings["speech_render_ms"]
    assert "audio_base64" not in payload
