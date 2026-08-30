"""Deterministic verifier for the MaryV2 convergence upgrade."""
from __future__ import annotations

from mary.core.mary import Mary
from mary.creative import ProductionFormat, Shot, build_production_plan, capability_jobs
from mary.runtime.root_authority import MaryRootAuthority


def main() -> int:
    mary = Mary()
    checks = []

    def check(label: str, condition: bool) -> None:
        checks.append((label, bool(condition)))

    check("one Mary root authority installed", isinstance(mary.root_authority, MaryRootAuthority))
    check("character sourcebook installed", getattr(mary, "character_sourcebook", None) is not None)
    check("TurnMind shares character sourcebook", mary.turn_mind.character_sourcebook is mary.character_sourcebook)
    check("Mary evaluation set installed", getattr(mary, "character_evaluation", None) is not None)
    check("creative service catalog installed", getattr(mary, "creative_services", None) is not None)
    check("root authority validates live Mary", not mary.root_authority.validate(mary))
    check("system contract validates live Mary", not mary.system_contract.validate(mary))

    plan = build_production_plan(
        title="Convergence verifier",
        objective="Prove cross-media capability planning without execution",
        shots=[Shot("unit-1", 1.0, "scene", "Mary reviews a storyboard")],
        format=ProductionFormat.ANIMATION.value,
        budget_ceiling_usd=5.0,
    )
    jobs = capability_jobs(plan)
    check("animation production plans reference + motion + edit jobs", [x["kind"] for x in jobs] == ["image.generate", "video.render", "edit.assemble"])
    check("creative planning does not silently authorize jobs", all(bool(x.get("requires_approval")) for x in jobs))

    print("=" * 72)
    print("MARYV2 CONVERGENCE VERIFICATION")
    print("=" * 72)
    for label, ok in checks:
        print(f"{'PASS' if ok else 'FAIL'}  {label}")
    print("=" * 72)
    if all(ok for _, ok in checks):
        print("MARYV2 CONVERGENCE INSTALLED CORRECTLY")
        return 0
    print("MARYV2 CONVERGENCE VERIFICATION FAILED")
    return 1


if __name__ == "__main__":
    raise SystemExit(main())
