"""Deterministic verifier for MaryV2 12.12.2 natural conversation calibration."""
from __future__ import annotations

from pathlib import Path

from mary.expression.director import ExpressionDirector
from mary.expression.emotion import Emotion, EmotionalState
from mary.mind.local_models import CANDIDATES
from mary.runtime.release import APP_VERSION
from mary.voice.speech_renderer import SpeechRenderer

ROOT = Path(__file__).resolve().parents[1]


def check(condition: bool, message: str) -> bool:
    print(f"[{'OK' if condition else 'FAIL'}] {message}")
    return bool(condition)


def main() -> int:
    print("=" * 76)
    print("MARYV2 12.12.2 NATURAL CONVERSATION + LOCAL LAB")
    print("=" * 76)
    checks: list[bool] = []
    checks.append(check(APP_VERSION in {"12.12.2", "13.0.0", "13.1.1"}, "natural-conversation foundation remains installed in current release"))
    for relative in (
        "mary/desktop/audio_cache.py",
        "scripts/voice_lab.py",
        "scripts/run_voice_lab_windows.ps1",
        "scripts/list_windows_tts_voices.ps1",
        "docs/history/root-archive/release-notes/START_HERE_12_12_2.md",
        "docs/operations/CODEX_WORKFLOW.md",
        ".vscode/tasks.json",
        "tests/expression/test_natural_conversation_12_12_2.py",
        "tests/desktop/test_audio_transport_12_12_2.py",
        "tests/llm/test_local_model_lab_12_12_2.py",
    ):
        checks.append(check((ROOT / relative).is_file(), f"surface exists: {relative}"))

    plan = ExpressionDirector().plan(
        input_text="hey mary",
        response_text="Hey. I'm here.",
        emotional_state=EmotionalState(primary=Emotion.NEUTRAL, intensity=0.0),
        conversation_lane="social_instant",
        dialogue_act="greet",
    )
    checks.append(check(plan.stability >= .5 and plan.style <= .05 and plan.gesture_energy <= .25, "ordinary social delivery is restrained"))
    checks.append(check(plan.metadata.get("performance_mode") == "natural_conversation", "natural-conversation performance mode is explicit"))
    checks.append(check("..." not in SpeechRenderer().render("Well... okay!!"), "speech renderer reduces dramatic pause cues"))

    models = {item.model for item in CANDIDATES}
    checks.append(check({"qwen3:1.7b", "llama3.2:1b", "gemma3:1b", "smollm2:1.7b", "llama3.2:3b", "phi4-mini", "qwen3:4b"}.issubset(models), "expanded local model bench is installed"))

    js = (ROOT / "desktop/src/main.js").read_text(encoding="utf-8")
    bridge = (ROOT / "mary/desktop/bridge.py").read_text(encoding="utf-8")
    checks.append(check("voice.audio_url" in js and "audioSourceFromVoice" in js, "desktop prefers local-file audio transport"))
    checks.append(check("voicePlaybackStage" in js and "voicePlaybackStage" in bridge, "playback startup stages are instrumented"))
    checks.append(check("addEventListener('playing'" in js, "lip sync waits for actual playback start"))

    reasoning = (ROOT / "mary/cognition/reasoning.py").read_text(encoding="utf-8")
    natural_direction = (
        "Sound like Mary is simply talking, not performing" in reasoning
        or ("Voice/avatar acting is handled by the performance layer" in reasoning and "Speak naturally as Mary rather than as a helpdesk assistant" in reasoning)
    )
    bounded_dialogue = (
        "token budget as a ceiling" in reasoning
        or "Ordinary chat is usually one to four sentences" in reasoning
    )
    checks.append(check(natural_direction, "model dialogue receives natural-conversation direction"))
    checks.append(check(bounded_dialogue, "ordinary conversation is explicitly bounded instead of filling its token budget"))

    ok = all(checks)
    print("=" * 76)
    print("MARYV2 12.12.2 VERIFIED" if ok else "MARYV2 12.12.2 VERIFICATION FAILED")
    return 0 if ok else 1


if __name__ == "__main__":
    raise SystemExit(main())
