"""Offline verifier for MaryV2 12.8 Ecosystem + Presence."""
from __future__ import annotations
import os
from pathlib import Path
import tempfile

from mary.core.mary import Mary
from mary.ecosystem import MaryEcosystem
from mary.presence import PresenceEventType
from mary.skills import SkillRegistry
from mary.runtime.release import APP_VERSION, DESKTOP_PHASE

ROOT=Path(__file__).resolve().parents[1]

def check(label,condition):
    if not condition: raise AssertionError(label)
    print(f"PASS  {label}")

def main()->int:
    print("="*72); print("MARYV2 12.8 ECOSYSTEM + PRESENCE"); print("="*72)
    check("12.8 ecosystem remains present under current release",APP_VERSION in {"12.8.0", "12.9.0", "12.10.0", "12.11.0", "12.12.0", "12.12.2"} and DESKTOP_PHASE in {"ecosystem-presence-beta", "desktop-uplift-runtime", "presence-presentation", "fast-dialogue-connected-presence", "cognitive-reservoir-character-runtime"})
    required=(
        "mary/ecosystem/manager.py","mary/productivity/command_center.py","mary/productivity/focus.py","mary/productivity/search.py",
        "mary/study/manager.py","mary/presence/manager.py","mary/presence/initiative.py","mary/skills/registry.py",
        "desktop/design/MARY_12_8_ECOSYSTEM_TARGET.png","desktop/public/assets/ui/mary-sigil.svg","desktop/public/assets/sounds/startup.wav",
        "scripts/setup_local_voice_windows.ps1","requirements-local-voice.txt",
    )
    for relative in required: check(f"12.8 surface exists: {relative}",(ROOT/relative).exists())
    js=(ROOT/"desktop/src/main.js").read_text(encoding="utf-8")
    html=(ROOT/"desktop/index.html").read_text(encoding="utf-8")
    voice=(ROOT/"mary/desktop/voice.py").read_text(encoding="utf-8")
    check("desktop exposes ecosystem workspaces",all(x in js for x in ("renderStudy","renderCommand","renderFocus","renderStream","renderSearch","renderArcade","renderDiagnostics")))
    check("game shell keeps persistent Mary chat", "composer-deck" in html and "MaryCosma.vrm" in js)
    check("boot polish uses bundled local assets","boot-screen" in html and "startup.wav" in html and "https://" not in (ROOT/"desktop/public/assets/ui/mary-sigil.svg").read_text(encoding="utf-8"))
    check("local voice has Piper and Windows SAPI with cloud opt-in","piper" in voice.lower() and "windows_sapi" in voice and "MARY_TTS_ALLOW_CLOUD_FALLBACK" in voice)
    skills=SkillRegistry()
    check("core ecosystem skills enabled",skills.enabled("study") and skills.enabled("focus") and skills.enabled("presence"))
    check("external skills default disabled",not skills.enabled("twitch") and not skills.enabled("obs") and not skills.enabled("vision"))
    old=os.environ.get("MARY_DATA_DIR")
    try:
        with tempfile.TemporaryDirectory(prefix="maryv2_12_8_") as directory:
            data=Path(directory)/"data"; os.environ["MARY_DATA_DIR"]=str(data)
            mary=Mary(); eco=MaryEcosystem(mary)
            eco.command.add("Verifier task")
            project=eco.study.create_project("Verifier study")
            eco.study.add_card(project["id"],"Question","Answer")
            event=eco.presence.publish(PresenceEventType.VISUAL_OBSERVATION,"A safe visual summary",source="visual",metadata={"screenshot":"SECRET","application":"Test"})
            check("ecosystem persists beneath canonical Mary data root",eco.root==data/"ecosystem" and (eco.root/"command_center.json").exists())
            check("raw visual material is stripped","SECRET" not in repr(event) and event["event"]["metadata"].get("application")=="Test")
            check("presence can choose silence",eco.presence.publish(PresenceEventType.IDLE_TICK,"quiet",source="idle",importance=.1)["decision"]["speak"] is False)
            snapshot=eco.snapshot()
            check("dashboard ecosystem snapshot is bounded and credential-free","GROQ_API_KEY" not in repr(snapshot) and "OPENAI_API_KEY" not in repr(snapshot))
    finally:
        if old is None: os.environ.pop("MARY_DATA_DIR",None)
        else: os.environ["MARY_DATA_DIR"]=old
    print("="*72); print("MARYV2 12.8 ECOSYSTEM + PRESENCE VERIFIED"); return 0

if __name__=="__main__": raise SystemExit(main())
