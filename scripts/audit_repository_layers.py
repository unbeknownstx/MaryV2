"""Classify MaryV2 repository layers without deleting anything."""
from __future__ import annotations
import argparse
from datetime import datetime, timezone
import json
from pathlib import Path
from typing import Any


CANONICAL_DIRS = {"mary", "tests", "scripts", "docs", "desktop", "mobile_web", "mobile_native", "character_sources", "projects"}
PRIVATE_DIRS = {"data", ".git", ".venv", "node_modules", ".test-tmp", ".tmp"}
GENERATED_DIRS = {"__pycache__", ".pytest_cache", "dist", "build", "runtime_reports"}
HISTORY_DIRS = {"archive", "archives"}
HISTORY_PREFIXES = (
    "START_HERE_", "TEST_RESULTS_", "MIGRATION_", "CHECKPOINT_", "FINAL_PASS_",
    "DESKTOP_PHASE_", "MOBILE_", "STAGE", "MARYV2_12_", "MARYV2_13_",
)
ROOT_CANONICAL_FILES = {
    "README.md", "AGENTS.md", "CODEX_WORKFLOW.md", "DEVELOPMENT_PLAN.md",
    "pyproject.toml", "requirements.txt", "package.json", "package-lock.json",
    ".gitignore", ".env.example", "run_mary.py",
    "MARY_ROOT.md", "MARYV2_CONVERGENCE_UPGRADE.md",
}


def classify(path: Path, root: Path) -> str:
    rel = path.relative_to(root)
    parts = rel.parts
    name = path.name
    if name == ".env" or name.startswith(".env.") and name != ".env.example":
        return "private_runtime_state"
    if parts and parts[0] in PRIVATE_DIRS:
        return "private_or_environment"
    if any(part in GENERATED_DIRS for part in parts):
        return "generated"
    if parts and parts[0] in HISTORY_DIRS:
        return "historical_archive_candidate"
    if len(parts) == 1 and name in ROOT_CANONICAL_FILES:
        return "canonical_or_active_support"
    if len(parts) == 1 and name.startswith(HISTORY_PREFIXES):
        return "historical_document_archive_candidate"
    if parts and parts[0] in CANONICAL_DIRS:
        return "canonical_working_tree"
    if name.endswith((".patch", ".diff")) or "HOTFIX" in name.upper():
        return "historical_patch_review"
    return "manual_review"


def audit(root: Path) -> dict[str, Any]:
    rows = []
    counts: dict[str, int] = {}
    for item in sorted(root.iterdir(), key=lambda x: x.name.lower()):
        category = classify(item, root)
        counts[category] = counts.get(category, 0) + 1
        rows.append({
            "path": item.name,
            "type": "directory" if item.is_dir() else "file",
            "classification": category,
        })
    return {
        "version": "1.0",
        "created_at": datetime.now(timezone.utc).isoformat(),
        "root": str(root.resolve()),
        "destructive": False,
        "counts": counts,
        "items": rows,
        "policy": [
            "Inventory first; classify second; archive third; delete only with separate evidence and backup.",
            "Historical docs/patches are provenance and may encode semantic predecessors until reconciled.",
            "Private runtime state and secrets must never be moved into release/source archives by this tool.",
            "This audit performs no filesystem mutations.",
        ],
    }


def markdown(report: dict[str, Any]) -> str:
    lines = [
        "# MaryV2 Repository Layer Audit",
        "",
        "> Read-only classification. Nothing was moved or deleted.",
        "",
        "| Path | Type | Classification |",
        "|---|---|---|",
    ]
    for item in report["items"]:
        lines.append(f"| `{item['path']}` | {item['type']} | `{item['classification']}` |")
    lines += ["", "## Policy", ""] + [f"- {x}" for x in report["policy"]]
    return "\n".join(lines) + "\n"


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--root", default=".")
    parser.add_argument("--json", default="MARYV2_REPOSITORY_LAYER_AUDIT.json")
    parser.add_argument("--markdown", default="MARYV2_REPOSITORY_LAYER_AUDIT.md")
    args = parser.parse_args()
    root = Path(args.root).expanduser().resolve()
    report = audit(root)
    Path(args.json).write_text(json.dumps(report, indent=2, ensure_ascii=False), encoding="utf-8")
    Path(args.markdown).write_text(markdown(report), encoding="utf-8")
    print(json.dumps(report["counts"], indent=2))
    print("READ ONLY: no files were moved or deleted.")
    return 0

if __name__ == "__main__":
    raise SystemExit(main())
