"""Offline verifier for MaryV2 12.9 Desktop Uplift + Runtime Instrumentation."""
from __future__ import annotations

import json
from pathlib import Path

from mary.runtime.release import APP_VERSION, DESKTOP_PHASE
from mary.productivity.metrics import RuntimeMetrics
from mary.desktop.voice import DesktopVoiceEngine

ROOT = Path(__file__).resolve().parents[1]


def check(label: str, condition: bool) -> None:
    if not condition:
        raise AssertionError(label)
    print(f"[OK] {label}")


def main() -> int:
    print("=" * 72)
    print("MARYV2 12.9 DESKTOP UPLIFT + RUNTIME INSTRUMENTATION")
    print("=" * 72)

    check("12.9 uplift remains installed under current release", APP_VERSION in {"12.9.0", "12.10.0", "12.11.0", "12.12.0", "12.12.2", "13.0.0", "13.1.1"})
    check("uplift runtime remains installed under current phase", DESKTOP_PHASE in {"desktop-uplift-runtime", "presence-presentation", "fast-dialogue-connected-presence", "cognitive-reservoir-character-runtime", "connected-development-evolution", "realtime-cognitive-infrastructure"})

    required = (
        "mary/desktop/turn_trace.py",
        "mary/productivity/metrics.py",
        "desktop/src/runtime/turnTrace.js",
        "desktop/src/uplift.css",
        "START_HERE_12_9.md",
    )
    for relative in required:
        check(f"uplift surface exists: {relative}", (ROOT / relative).is_file())

    html = (ROOT / "desktop/index.html").read_text(encoding="utf-8")
    js = (ROOT / "desktop/src/main.js").read_text(encoding="utf-8")
    css = (ROOT / "desktop/src/uplift.css").read_text(encoding="utf-8")
    bridge = (ROOT / "mary/desktop/bridge.py").read_text(encoding="utf-8")
    router = (ROOT / "mary/llm/router.py").read_text(encoding="utf-8")
    reasoning = (ROOT / "mary/cognition/reasoning.py").read_text(encoding="utf-8")

    check("Runtime workspace is visible", 'data-screen="diagnostics"' in html)
    check("right-rail live turn HUD is visible", 'id="runtime-perceived"' in html)
    check("frontend consumes measured traces", "applyTurnTrace" in js and "providerAttemptSummary" in js)
    check("responsive laptop breakpoint exists", "@media (max-width: 1099px)" in css)
    check("desktop bridge exposes last trace", "getLastTurnTrace" in bridge)
    check("desktop bridge measures playback start", "voice_playback_started" in bridge)
    check("router records provider-call latency", '"call_ms": provider_call_ms' in router)
    check("micro social token budget is installed", 'if preferred == "micro"' in reasoning and "return 160" in reasoning)

    metrics = RuntimeMetrics()
    metrics.record_turn_trace({"provider": "local/system", "timings": {"pipeline_ms": 10.0}})
    check("runtime metric trace records", metrics.snapshot().get("pipeline_ms", {}).get("last_ms") == 10.0)
    check("voice timing metadata records while disabled", "timings" in DesktopVoiceEngine().synthesize("hello"))

    package = json.loads((ROOT / "PACKAGE_INFO.json").read_text(encoding="utf-8"))
    check("package metadata is 12.9 or later", package.get("version") in {"12.9.0", "12.10.0", "12.11.0", "12.12.0", "12.12.2", "13.0.0", "13.1.1"})

    print("=" * 72)
    print("MARYV2 12.9 UPLIFT VERIFIED")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
