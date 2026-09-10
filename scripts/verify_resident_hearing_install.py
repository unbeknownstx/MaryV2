from __future__ import annotations

from pathlib import Path


def main() -> int:
    root = Path(__file__).resolve().parents[1]
    resident = (root / 'mary' / 'desktop' / 'resident_hearing.py').read_text(encoding='utf-8')
    bridge = (root / 'mary' / 'desktop' / 'bridge.py').read_text(encoding='utf-8')
    frontend = (root / 'desktop' / 'src' / 'main.js').read_text(encoding='utf-8')

    checks = [
        ('class EnergyVadDetector' in resident, 'local VAD detector is installed'),
        ('self._enabled = False' in resident, 'Resident Hearing starts OFF'),
        ('QAudioSource' in resident, 'resident capture uses local Qt audio'),
        ('raw audio local only' in resident, 'privacy boundary is explicit'),
        ('def setResidentHearing' in bridge, 'bridge exposes explicit resident toggle'),
        ('resident_hearing.disable()' in bridge, 'desktop shutdown disarms microphone'),
        ('source="desktop_resident_vad"' in bridge, 'bounded VAD state reaches realtime coordinator'),
        ('resident-hearing-toggle' in frontend, 'Voice screen exposes Resident Hearing control'),
        ('bridge.startListening()' in frontend, 'existing push-to-talk remains installed'),
    ]

    print('MARYV2 13.4 CONTROLLED RESIDENT HEARING VERIFICATION')
    print('=' * 72)
    failed = 0
    for ok, label in checks:
        print(('PASS' if ok else 'FAIL').ljust(6), label)
        if not ok:
            failed += 1
    print('=' * 72)
    if failed:
        print(f'FAILED: {failed} check(s)')
        return 1
    print('CONTROLLED RESIDENT HEARING INSTALLED CORRECTLY')
    return 0


if __name__ == '__main__':
    raise SystemExit(main())
