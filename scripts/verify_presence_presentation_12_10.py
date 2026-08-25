"""Offline verifier for MaryV2 12.10 Presence + Presentation."""
from __future__ import annotations

import json
import os
from pathlib import Path
from tempfile import TemporaryDirectory

from mary.core.mary import Mary
from mary.ecosystem import MaryEcosystem
from mary.presence import PresenceEventType
from mary.runtime.release import APP_VERSION, DESKTOP_PHASE

ROOT = Path(__file__).resolve().parents[1]


def check(label: str, condition: bool) -> None:
    if not condition:
        raise AssertionError(label)
    print(f"[OK] {label}")


def main() -> int:
    print("=" * 72)
    print("MARYV2 12.10 PRESENCE + PRESENTATION")
    print("=" * 72)

    check("12.10 presentation remains installed under current release", APP_VERSION in {"12.10.0", "12.11.0", "12.12.0", "12.12.2", "13.0.0", "13.1.1"})
    check("presence presentation remains installed under current phase", DESKTOP_PHASE in {"presence-presentation", "fast-dialogue-connected-presence", "cognitive-reservoir-character-runtime", "connected-development-evolution", "realtime-cognitive-infrastructure"})

    required = (
        "mary/ecosystem/companion.py",
        "desktop/src/ui/presenceHome.js",
        "desktop/src/presence.css",
        "tests/integration/test_presence_pathways_12_10.py",
        "tests/desktop/test_presence_presentation_12_10.py",
        "START_HERE_12_10.md",
    )
    for relative in required:
        check(f"12.10 surface exists: {relative}", (ROOT / relative).is_file())

    html = (ROOT / "desktop/index.html").read_text(encoding="utf-8")
    js = (ROOT / "desktop/src/main.js").read_text(encoding="utf-8")
    css = (ROOT / "desktop/src/presence.css").read_text(encoding="utf-8")
    vite = (ROOT / "desktop/vite.config.js").read_text(encoding="utf-8")
    bridge = (ROOT / "mary/desktop/bridge.py").read_text(encoding="utf-8")

    check("Mary Home navigation is visible", 'data-screen="home"' in html)
    check("companion pulse is visible in right rail", 'id="companion-pulse-card"' in html)
    check("portrait art presentation remains local", "data-avatar-presentation" in js and "mary-reference.jpeg" in html)
    check("live VRM remains connected", "MaryCosma.vrm" in js and "loadMaryVrm" in js)
    check("focus-aware chrome is installed", 'data-focus="active"' in css)
    check("Vite config uses import.meta.dirname", "import.meta.dirname" in vite and "__dirname" not in vite)
    check("Vite config uses Rolldown code splitting", "codeSplitting" in vite and "three-runtime" in vite)
    check("workspace actions publish typed presence context", "PresenceEventType.COMMAND_CHANGED" in bridge and "PresenceEventType.CREATIVE_CHANGED" in bridge)

    old_data = os.environ.get("MARY_DATA_DIR")
    try:
        with TemporaryDirectory(prefix="maryv2_12_10_verify_") as tmp:
            os.environ["MARY_DATA_DIR"] = str(Path(tmp) / "data")
            mary = Mary()
            ecosystem = MaryEcosystem(mary)
            ecosystem.command.add("Verifier command item")
            project = ecosystem.study.create_project("Verifier study")
            ecosystem.study.add_card(project["id"], "One?", "One.")
            ecosystem.inbox.add("Verifier quiet notice")
            pulse = ecosystem.companion_snapshot()
            check("companion pulse reads command state", pulse["counts"]["active_tasks"] == 1)
            check("companion pulse reads study state", pulse["counts"]["study_due"] == 1)
            check("companion pulse reads inbox state", pulse["counts"]["inbox_unread"] == 1)
            check("companion pulse has no separate persistent owner", not (ecosystem.root / "companion.json").exists())
            focus = ecosystem.publish_workspace_event(PresenceEventType.FOCUS_CHANGED, "Focus started", importance=.65)
            check("focus context stays quiet", focus["decision"]["speak"] is False)
            idle = ecosystem.presence.idle_tick(focus_active=True)
            check("focus idle behavior is animation-only", idle["focus_quiet"] and idle["action"]["kind"] == "animation")
    finally:
        if old_data is None:
            os.environ.pop("MARY_DATA_DIR", None)
        else:
            os.environ["MARY_DATA_DIR"] = old_data

    package = json.loads((ROOT / "PACKAGE_INFO.json").read_text(encoding="utf-8"))
    check("package metadata is 12.10 or later", package.get("version") in {"12.10.0", "12.11.0", "12.12.0", "12.12.2", "13.0.0", "13.1.1"} and package.get("desktop_phase") in {"presence-presentation", "fast-dialogue-connected-presence", "cognitive-reservoir-character-runtime", "connected-development-evolution", "realtime-cognitive-infrastructure"})

    print("=" * 72)
    print("MARYV2 12.10 PRESENCE + PRESENTATION VERIFIED")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
