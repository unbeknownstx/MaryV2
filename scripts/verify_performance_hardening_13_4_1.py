from __future__ import annotations

from pathlib import Path


def main() -> int:
    root = Path(__file__).resolve().parents[1]
    required = (
        "mary/realtime/presentation_session.py",
        "mary/streaming/input_governor.py",
        "mary/expression/standing_affect.py",
        "mary/avatar/transport_guard.py",
        "mary/distributed/stream_capabilities.py",
        "mary/runtime/performance_hardening.py",
    )
    missing = [item for item in required if not (root / item).exists()]
    mary = (root / "mary/core/mary.py").read_text(encoding="utf-8")
    realtime = (root / "mary/realtime/interaction.py").read_text(encoding="utf-8")
    stream = (root / "mary/streaming/presence.py").read_text(encoding="utf-8")
    checks = (
        (not missing, "hardening modules exist"),
        ("install_performance_hardening" in mary, "canonical Mary installs hardening"),
        ("PresentationSessionManager" in realtime, "realtime owns presentation sessions"),
        ("StreamInputGovernor" in stream, "stream input governor is wired before Presence"),
        ("conversation_appraisal" in mary, "standing affect stores no raw turn text"),
    )
    failed = 0
    print("MARYV2 13.4.1 PERFORMANCE HARDENING VERIFICATION")
    print("=" * 72)
    for ok, label in checks:
        print(("PASS" if ok else "FAIL").ljust(6), label)
        failed += 0 if ok else 1
    for item in missing:
        print("FAIL  missing", item)
        failed += 1
    return 1 if failed else 0


if __name__ == "__main__":
    raise SystemExit(main())
