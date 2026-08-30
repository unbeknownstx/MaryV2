"""Fail-fast structural hygiene gate for the canonical MaryV2 source tree."""
from __future__ import annotations

from pathlib import Path
import sys

ROOT = Path(__file__).resolve().parents[1]

REQUIRED = (
    "README.md",
    "MARY_ROOT.md",
    "AGENTS.md",
    "mary",
    "tests",
    "scripts",
    "docs/architecture/SYSTEM_REGISTRY.md",
    "character_sources/active",
    "character_sources/drafts",
    "projects/unbeknownst",
)
FORBIDDEN_ROOT_DIRS = {
    "data", "payload", "upgrade_backups", "attached_assets", "Unbeknownst Chapters", "node_modules",
}
HISTORY_PREFIXES = (
    "START_HERE_", "TEST_RESULTS_", "MIGRATION_", "CHECKPOINT_", "FINAL_PASS_",
    "DESKTOP_PHASE_", "MOBILE_", "STAGE", "BREAKTHROUGH_", "MARYV2_12_", "MARYV2_13_",
)


def violations(root: Path = ROOT) -> list[str]:
    errors: list[str] = []
    for rel in REQUIRED:
        if not (root / rel).exists():
            errors.append(f"missing required path: {rel}")

    for name in sorted(FORBIDDEN_ROOT_DIRS):
        if (root / name).exists():
            errors.append(f"forbidden active root directory: {name}")

    if (root / "desktop" / "node_modules").exists():
        errors.append("desktop/node_modules must be regenerated with npm ci, never tracked as source")

    for item in root.iterdir():
        if item.is_file() and item.name.startswith(HISTORY_PREFIXES):
            errors.append(f"historical root file belongs under docs/history: {item.name}")
        if item.is_file() and (item.suffix.lower() in {".patch", ".diff"} or "HOTFIX" in item.name.upper()):
            errors.append(f"historical patch/hotfix belongs under docs/history: {item.name}")

    for base in (root / "mary", root / "tests", root / "scripts"):
        if not base.exists():
            continue
        for path in base.rglob("*"):
            if path.is_file() and (".pre_" in path.name or ".bak" in path.name):
                errors.append(f"source backup copy must not live in canonical tree: {path.relative_to(root)}")

    return errors


def main() -> int:
    errors = violations()
    print("MARYV2 REPOSITORY STRUCTURE")
    print("=" * 64)
    if errors:
        for item in errors:
            print(f"FAIL  {item}")
        print(f"{len(errors)} structural violation(s)")
        return 1
    print("PASS  canonical root is clean")
    print("PASS  historical material is separated from active source")
    print("PASS  mutable runtime state/dependency outputs are outside source")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
