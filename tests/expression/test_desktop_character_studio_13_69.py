from __future__ import annotations

from pathlib import Path


ROOT = Path(__file__).resolve().parents[2]


def test_desktop_character_studio_reuses_canonical_renderer():
    source = (ROOT / "desktop" / "src" / "main.js").read_text(encoding="utf-8")

    assert "CHARACTER STUDIO" in source
    assert "applyStageLighting" in source
    assert "data-stage-expression" in source
    assert "data-stage-motion" in source
    assert "data-stage-lighting" in source
    assert "captureAvatarPng" in source
    assert "copyStageSetup" in source
    assert "authority: 'presentation_only'" in source
    assert "studioMotionCue" in source
    assert "currentMotionCue" in source


def test_desktop_character_studio_keeps_cognition_out_of_renderer_controls():
    source = (ROOT / "desktop" / "src" / "main.js").read_text(encoding="utf-8")
    start = source.index("function applyStageLighting")
    end = source.index("let previousFrameMs", start)
    block = source[start:end]

    assert "bridge.sendMessage" not in block
    assert "memory" not in block.lower()
    assert "relationship" not in block.lower()
    assert "tool" not in block.lower()
