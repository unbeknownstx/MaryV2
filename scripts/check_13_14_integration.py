"""Read-only convergence check for MaryV2 13.14 research-derived upgrades."""
from __future__ import annotations

from mary.character import CharacterSourcebook
from mary.distributed import SPECIALIST_CATALOG, specialist_status
from mary.distributed.sensors import SENSOR_CAPABILITIES, SCREEN_DESCRIBE_CAPABILITY
from mary.learning.interop import records_from_evaluation_set
from mary.character import MaryEvaluationSet
from scripts.platform_readiness import collect_readiness


def main() -> int:
    checks: list[tuple[str, bool]] = []

    def check(label: str, condition: bool) -> None:
        checks.append((label, bool(condition)))

    sourcebook = CharacterSourcebook.empty()
    source_snapshot = sourcebook.snapshot()
    check("canonical sourcebook has structured intelligence", source_snapshot.get("structured_character_intelligence") is True)
    check("sourcebook does not own lived AI memory", source_snapshot.get("semantics", {}).get("ai_lived_memory_owner") is False)
    check("semantic screen sensor registered", SCREEN_DESCRIBE_CAPABILITY in SENSOR_CAPABILITIES)
    check("specialist catalog present", len(SPECIALIST_CATALOG) >= 10)
    specialist = specialist_status()
    check("specialists are not Core startup dependencies", specialist.get("semantics", {}).get("core_startup_dependency") is False)
    check("specialists have no external identity authority", specialist.get("semantics", {}).get("external_identity_authority") is False)
    check("MaryBench conversion is available", isinstance(records_from_evaluation_set(MaryEvaluationSet.empty()), list))
    readiness = collect_readiness()
    check("platform readiness exposes specialist status", isinstance(readiness.get("specialist_backends"), dict))
    check("platform readiness adds no shell surface", readiness.get("shell_execution_surface_added") is False)

    print("MARYV2 13.14 INTEGRATION")
    print("=" * 64)
    for label, passed in checks:
        print(f"{'PASS' if passed else 'FAIL'}  {label}")
    failed = [label for label, passed in checks if not passed]
    print("=" * 64)
    print(f"{len(checks) - len(failed)}/{len(checks)} checks passed")
    return 1 if failed else 0


if __name__ == "__main__":
    raise SystemExit(main())
