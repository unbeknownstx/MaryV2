from __future__ import annotations

from pathlib import Path

from mary.cognition.context import CognitiveContext
from mary.cognition.intent import IntentType
from mary.cognition.mind_state import TurnMindStateBuilder
from mary.cognition.reasoning import ReasoningEngine
from mary.desktop.voice import DesktopVoiceEngine
from mary.productivity.metrics import RuntimeMetrics


ROOT = Path(__file__).resolve().parents[2]


def text(relative: str) -> str:
    return (ROOT / relative).read_text(encoding="utf-8")


def test_12_9_release_metadata_and_runtime_surface_are_packaged():
    release = text("mary/runtime/release.py")
    html = text("desktop/index.html")
    assert 'APP_VERSION = "12.9.0"' in release
    assert 'DESKTOP_PHASE = "desktop-uplift-runtime"' in release
    assert 'data-screen="diagnostics"' in html
    assert 'id="runtime-perceived"' in html
    assert (ROOT / "desktop/src/runtime/turnTrace.js").is_file()
    assert (ROOT / "desktop/src/uplift.css").is_file()


def test_runtime_metrics_keep_bounded_last_turn_trace_without_private_text():
    metrics = RuntimeMetrics(limit=10)
    trace = {
        "turn_id": "turn_demo",
        "provider": "groq",
        "model": "demo-model",
        "timings": {"pipeline_ms": 1250.0, "tts_synthesis_ms": 240.0},
    }
    metrics.record_turn_trace(trace)
    snap = metrics.snapshot()
    assert snap["pipeline_ms"]["last_ms"] == 1250.0
    assert snap["tts_synthesis_ms"]["last_ms"] == 240.0
    assert metrics.last_turn()["provider"] == "groq"
    assert "prompt" not in metrics.last_turn()


def test_voice_payload_reports_render_and_synthesis_timings_even_when_disabled():
    payload = DesktopVoiceEngine().synthesize("Hey Mary")
    assert payload["status"] == "disabled"
    assert payload["timings"]["speech_render_ms"] >= 0
    assert payload["timings"]["tts_synthesis_ms"] == 0
    assert payload["timings"]["voice_total_ms"] >= payload["timings"]["speech_render_ms"]


def test_micro_social_disposition_and_completion_budget():
    builder = object.__new__(TurnMindStateBuilder)
    disposition = builder._build_disposition(
        input_text="holy damn youre actually here",
        intent_type=IntentType.CONVERSATION,
        personality={"traits": {"warmth": 0.8, "curiosity": 0.8, "playfulness": 0.7, "independence": 0.6}, "style": {"verbosity": 0.5, "directness": 0.7, "formality": 0.3}},
        character={"behavior": {"expressiveness": 0.9, "sassiness": 0.6}, "speech": {}, "social_modes": {}, "reactions": {}},
        relationship={"current_profile": {}, "familiarity": "established"},
        agency={"active_curiosities": []},
        emotion={"primary": "excited", "intensity": 0.6, "turn_primary": "excited", "turn_intensity": 0.6},
        continuity={"drive": "react", "allow_follow_up_question": False, "instructions": []},
    )
    assert disposition.preferred_length == "micro"
    context = CognitiveContext(
        input_text="holy damn youre actually here",
        mind_state={"disposition": {"preferred_length": disposition.preferred_length}},
    )
    assert ReasoningEngine._conversation_max_tokens(context) == 160


def test_responsive_shell_matches_native_minimum_window_contract():
    css = text("desktop/src/uplift.css")
    window = text("mary/desktop/window.py")
    assert "min-width: 960px" in css
    assert "@media (max-width: 1099px)" in css
    assert "self.setMinimumSize(960, 620)" in window
    assert 'QSettings("Unbe", "MaryV2")' in window


def test_bridge_exposes_measured_turn_trace_without_creating_second_mary():
    bridge = text("mary/desktop/bridge.py")
    trace = text("mary/desktop/turn_trace.py")
    assert "build_turn_trace" in bridge
    assert "getLastTurnTrace" in bridge
    assert "voice_playback_started" in bridge
    assert "provider_call_ms" in trace
    assert "input_text" not in trace
    assert "response_text" not in trace
