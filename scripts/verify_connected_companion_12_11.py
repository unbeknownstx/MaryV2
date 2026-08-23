"""Deterministic verifier for MaryV2 12.11 connected-companion uplift."""
from __future__ import annotations

from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]


def _text(relative: str) -> str:
    return (ROOT / relative).read_text(encoding="utf-8")


def main() -> int:
    checks: list[tuple[bool, str]] = []
    release = _text("mary/runtime/release.py")
    router = _text("mary/llm/router.py")
    reflection = _text("mary/cognition/reflection.py")
    html = _text("desktop/index.html")
    js = _text("desktop/src/main.js")
    css = _text("desktop/src/neon-street.css")
    bridge = _text("mary/desktop/bridge.py")
    voice = _text("mary/desktop/voice.py")

    checks += [
        (('APP_VERSION = "12.11.0"' in release or ('APP_VERSION = "12.12.0"' in release or 'APP_VERSION = "12.12.2"' in release)), "software version preserves 12.11+ foundation"),
        (('DESKTOP_PHASE = "fast-dialogue-connected-presence"' in release or 'DESKTOP_PHASE = "cognitive-reservoir-character-runtime"' in release), "desktop phase preserves fast-dialogue connected presence"),
        ((ROOT / "mary/conversation/lanes.py").is_file(), "conversation lane classifier exists"),
        ((ROOT / "mary/conversation/reflection_policy.py").is_file(), "latency-aware reflection policy exists"),
        ("MARY_GROQ_CONVERSATION_MODEL" in router and "conversation_fast" in router, "purpose-specific fast Groq conversation model is wired"),
        ("local_fast_repair" in reflection, "style-only fast reflection can stay local"),
        ("auto_fast" in voice and "eleven_flash_v2_5" in voice, "auto-fast voice prefers configured ElevenLabs Flash with local fallback"),
        ((ROOT / "scripts/configure_fast_dialogue_windows.ps1").is_file(), "safe Windows fast-dialogue profile helper exists"),
        ((ROOT / "mary/integrations/youtube.py").is_file(), "explicit YouTube Data API adapter exists"),
        ((ROOT / "mary/presence/websocket_server.py").is_file(), "loopback read-only WebSocket presence transport exists"),
        ("searchYouTube" in bridge and "LocalPresenceWebSocket" in bridge, "desktop bridge exposes media + presence connections"),
        ('id="screen-launcher"' in html and 'id="ambient-audio"' in html, "workspace menu and ambient audio are packaged"),
        ("duckAmbientVolume" in js and "youtubeResults" in js, "frontend speech ducking and YouTube UI are wired"),
        ("--street-blue" in css and "screen-launcher-grid" in css, "blue-neon street clarity layer is installed"),
        ((ROOT / "desktop/public/assets/sounds/ambient_neon.wav").is_file(), "local ambient sound bed is packaged"),
        ((ROOT / "AGENTS.md").is_file(), "Codex/agent repository guidance is packaged"),
    ]

    print("=" * 72)
    print("MARYV2 12.11 FAST DIALOGUE + CONNECTED PRESENCE")
    print("=" * 72)
    failed = 0
    for ok, label in checks:
        print(f"[{'OK' if ok else 'FAIL'}] {label}")
        failed += 0 if ok else 1
    print("=" * 72)
    if failed:
        print(f"MARYV2 12.11 VERIFIER FAILED ({failed} checks)")
        return 1
    print("MARYV2 12.11 VERIFIED")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
