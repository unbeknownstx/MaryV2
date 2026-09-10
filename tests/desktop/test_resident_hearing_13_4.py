from __future__ import annotations

from pathlib import Path

from mary.desktop.resident_hearing import EnergyVadDetector, FRAME_MS


def _kinds(events):
    return [event.kind for event in events]


def test_energy_vad_requires_confirmation_before_speech():
    vad = EnergyVadDetector(
        calibration_ms=FRAME_MS * 4,
        confirm_ms=FRAME_MS * 3,
    )

    for _ in range(4):
        events = vad.observe(100)

    assert 'calibrated' in _kinds(events)
    assert _kinds(vad.observe(1000)) == ['candidate']
    assert _kinds(vad.observe(1000)) == []
    assert _kinds(vad.observe(1000)) == ['confirmed']


def test_energy_vad_ends_after_trailing_silence():
    vad = EnergyVadDetector(
        calibration_ms=FRAME_MS * 2,
        confirm_ms=FRAME_MS * 2,
        end_silence_ms=FRAME_MS * 3,
    )

    vad.observe(100)
    vad.observe(100)
    vad.observe(1000)
    vad.observe(1000)

    assert vad.state == 'confirmed'
    assert _kinds(vad.observe(0)) == []
    assert _kinds(vad.observe(0)) == []
    assert _kinds(vad.observe(0)) == ['end']
    assert vad.state == 'idle'


def test_energy_vad_false_start_never_becomes_confirmed_speech():
    vad = EnergyVadDetector(
        calibration_ms=FRAME_MS,
        confirm_ms=FRAME_MS * 3,
    )

    vad.observe(100)
    assert _kinds(vad.observe(1000)) == ['candidate']

    observed = []
    for _ in range(12):
        observed.extend(_kinds(vad.observe(100)))
        if 'false_start' in observed:
            break

    assert 'confirmed' not in observed
    assert 'false_start' in observed
    assert vad.state == 'idle'


def test_phase_2c_bridge_and_voice_ui_are_explicit_opt_in():
    root = Path(__file__).resolve().parents[2]
    bridge = (root / 'mary' / 'desktop' / 'bridge.py').read_text(encoding='utf-8')
    frontend = (root / 'desktop' / 'src' / 'main.js').read_text(encoding='utf-8')
    resident = (root / 'mary' / 'desktop' / 'resident_hearing.py').read_text(encoding='utf-8')

    assert 'DesktopResidentHearing()' in bridge
    assert 'def setResidentHearing' in bridge
    assert 'resident_hearing.disable()' in bridge
    assert 'residentHearingStateChanged' in bridge
    assert 'source="desktop_resident_vad"' in bridge
    assert "self._enabled = False" in resident
    assert 'raw audio local only' in resident
    assert 'resident-hearing-toggle' in frontend
    assert 'Turn Resident Hearing On' in frontend
    assert 'Push-to-talk remains available separately.' in frontend
