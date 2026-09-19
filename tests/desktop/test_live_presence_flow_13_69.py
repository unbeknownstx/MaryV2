from __future__ import annotations

from pathlib import Path


ROOT = Path(__file__).resolve().parents[2]


def test_desktop_exposes_live_presence_flow_without_new_state_authority():
    source = (ROOT / "desktop" / "src" / "main.js").read_text(encoding="utf-8")
    css = (ROOT / "desktop" / "src" / "presence-flow.css").read_text(encoding="utf-8")

    assert "presenceFlowMarkup" in source
    assert "syncPresenceFlow" in source
    assert "Identity" in source
    assert "Agency" in source
    assert "Embodiment" in source
    assert "Presence" in source
    assert "ephemeral telemetry only" in source
    assert "#ffd84d" in css
    assert ".pf-wire.active" in css
    assert "presence-current" in css


def test_presence_flow_reads_existing_runtime_state_only():
    source = (ROOT / "desktop" / "src" / "main.js").read_text(encoding="utf-8")
    start = source.index("function syncPresenceFlow()")
    end = source.index("function renderDiagnostics()", start)
    block = source[start:end]

    assert "conversationState" in block
    assert "currentPerformancePacket" in block
    assert "activeSpeechAudio" in block
    assert "bridge." not in block
    assert "localStorage.setItem" not in block
