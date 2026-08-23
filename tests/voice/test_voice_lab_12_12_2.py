from __future__ import annotations

from pathlib import Path


def test_voice_lab_is_offline_by_default_and_requires_explicit_synthesis():
    source = Path("scripts/voice_lab.py").read_text(encoding="utf-8")
    assert 'parser.add_argument("--synthesize", action="store_true"' in source
    assert "if not args.synthesize:" in source
    assert "MARY_ELEVENLABS_VOICE_CANDIDATES" in source
    assert "stability=.54" in source
