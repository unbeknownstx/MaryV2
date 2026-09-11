from __future__ import annotations

from pathlib import Path


def main() -> int:
    root = Path(__file__).resolve().parents[1]
    required = [
        root / "mary" / "continuity" / "__init__.py",
        root / "mary" / "continuity" / "runtime.py",
        root / "mary" / "continuity" / "experience.py",
        root / "mary" / "continuity" / "temporal.py",
        root / "mary" / "continuity" / "skills.py",
        root / "mary" / "continuity" / "workflows.py",
        root / "mary" / "continuity" / "verification.py",
        root / "mary" / "continuity" / "resources.py",
        root / "mary" / "continuity" / "prosody.py",
        root / "mary" / "continuity" / "trace.py",
    ]
    missing = [str(path.relative_to(root)) for path in required if not path.exists()]
    core = (root / "mary" / "core" / "mary.py").read_text(encoding="utf-8")
    backup = (root / "mary" / "runtime" / "backup.py").read_text(encoding="utf-8")
    checks = [
        (not missing, "all continuity modules exist"),
        ("ExperientialContinuityRuntime" in core, "canonical Mary composes continuity runtime"),
        ("self.experiential_continuity = ExperientialContinuityRuntime" in core, "experiential continuity composition root is installed without replacing TurnMind continuity"),
        ("continuity/experience.json" in backup, "experience ledger participates in state backup"),
        ("continuity/temporal_knowledge.json" in backup, "temporal history participates in state backup"),
        ("continuity/skills.json" in backup, "procedural skills participate in state backup"),
        ("continuity/workflows.json" in backup, "workflow checkpoints participate in state backup"),
        ("continuity/verification.json" in backup, "verification state participates in state backup"),
    ]
    print("MARYV2 13.4 EXPERIENTIAL CONTINUITY VERIFICATION")
    print("=" * 72)
    failed = 0
    for ok, label in checks:
        print(("PASS" if ok else "FAIL").ljust(6), label)
        failed += 0 if ok else 1
    for item in missing:
        print("FAIL  missing", item)
        failed += 1
    print("=" * 72)
    if failed:
        print(f"FAILED: {failed} check(s)")
        return 1
    print("EXPERIENTIAL CONTINUITY INSTALLED CORRECTLY")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
