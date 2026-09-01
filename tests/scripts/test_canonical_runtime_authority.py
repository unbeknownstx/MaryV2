from __future__ import annotations

import ast
from pathlib import Path


ROOT = Path(__file__).resolve().parents[2]


def _direct_mary_calls(path: Path) -> list[int]:
    tree = ast.parse(path.read_text(encoding="utf-8-sig"), filename=str(path))
    return sorted(
        node.lineno
        for node in ast.walk(tree)
        if isinstance(node, ast.Call)
        and isinstance(node.func, ast.Name)
        and node.func.id == "Mary"
    )


def _mary_process_calls(path: Path) -> list[int]:
    """Find direct coordinator turns that bypass MaryApplication.run."""

    tree = ast.parse(path.read_text(encoding="utf-8-sig"), filename=str(path))
    return sorted(
        node.lineno
        for node in ast.walk(tree)
        if isinstance(node, ast.Call)
        and isinstance(node.func, ast.Attribute)
        and node.func.attr == "process"
        and (
            isinstance(node.func.value, ast.Name)
            and node.func.value.id == "mary"
            or isinstance(node.func.value, ast.Attribute)
            and node.func.value.attr == "mary"
        )
    )


def _runtime_authority_violations(paths) -> dict[str, dict[str, list[int]]]:
    violations = {}
    for path in sorted(paths):
        direct = _direct_mary_calls(path)
        bypasses = _mary_process_calls(path)
        if direct or bypasses:
            violations[str(path.relative_to(ROOT))] = {
                **({"Mary()": direct} if direct else {}),
                **({"mary.process()": bypasses} if bypasses else {}),
            }
    return violations


def test_release_and_install_verifiers_use_canonical_runtime_composition():
    scripts = {
        ROOT / "scripts" / "benchmark_production_hybrid_dialogue.py",
        ROOT / "scripts" / "run_diagnostics.py",
        ROOT / "scripts" / "run_release_verification.py",
        *(ROOT / "scripts").glob("verify_*.py"),
    }
    violations = _runtime_authority_violations(scripts)

    assert violations == {}


def test_integration_tests_use_canonical_runtime_composition():
    violations = _runtime_authority_violations(
        (ROOT / "tests" / "integration").rglob("test_*.py")
    )

    assert violations == {}