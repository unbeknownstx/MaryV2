"""
MaryV2 release verification runner.

The release gate is offline and deterministic by default.

Default / --offline behavior:
    - compile Mary/source files
    - run the full normal pytest suite with MARY_RUN_LIVE_TESTS forcibly disabled
    - run system diagnostics
    - run every current deterministic verify_*.py milestone verifier
    - run local tool-safety smoke checks

Optional live checks are separate and explicit:
    --live-llm
        Run only tests/conversation/test_live_pipeline.py with
        MARY_RUN_LIVE_TESTS=1 after the offline gate.

    --live-web
        Perform one explicit live Tavily/Mary research request after the
        offline gate.

Use --offline when you want to state the offline-only intent explicitly.
It is also the default when no live flag is supplied.
"""

from __future__ import annotations

import argparse
import compileall
import importlib
import os
import subprocess
import sys
import tempfile
from pathlib import Path

from mary.core.diagnostics import MaryDiagnostics
from mary.core.mary import Mary
from mary.runtime.application import create_application
from mary.tools.manager import ToolManager


ROOT = Path(__file__).resolve().parents[1]
LIVE_LLM_TEST = "tests/conversation/test_live_pipeline.py"

# Keep this list explicit. New verify_*.py scripts must be deliberately added
# here rather than silently entering the release gate. A unit test guards that
# the registry stays synchronized with the scripts directory.
OFFLINE_VERIFIERS: tuple[tuple[str, str], ...] = (
    ("memory_restart", "scripts.verify_memory_restart"),
    ("provider_resilience", "scripts.verify_resilience_install"),
    ("self_introspection", "scripts.verify_self_introspection_install"),
    ("creator_directives", "scripts.verify_creator_directives_install"),
    ("relationship_development", "scripts.verify_relationship_development_install"),
    ("curiosity_development", "scripts.verify_curiosity_development_install"),
    ("priority_grounding", "scripts.verify_priority_grounding_install"),
    ("emotion_appraisal", "scripts.verify_emotion_appraisal_install"),
    ("desktop_alpha", "scripts.verify_desktop_alpha_install"),
    ("voice_input", "scripts.verify_voice_input_install"),
    ("conversation_runtime", "scripts.verify_conversation_runtime_install"),
    ("turn_mind", "scripts.verify_turn_mind_integration_install"),
    ("conversation_continuity", "scripts.verify_conversation_continuity_install"),
    ("context_lifecycle", "scripts.verify_context_lifecycle"),
    ("performance_pass", "scripts.verify_performance_pass_install"),
    ("long_session_hardening", "scripts.verify_long_session_hardening"),
    ("developed_self_persistence", "scripts.verify_developed_self_persistence"),
    ("preference_promotion", "scripts.verify_preference_promotion"),
    ("natural_relationship_learning", "scripts.verify_natural_relationship_learning"),
    ("multi_provider_router", "scripts.verify_multi_provider_router_install"),
    ("provider_routing_guarantees", "scripts.verify_provider_routing_guarantees"),
    ("task_workspace", "scripts.verify_task_workspace"),
    ("openai_expert", "scripts.verify_openai_expert_install"),
    ("task_orchestrator", "scripts.verify_task_orchestrator"),
    ("orchestration_execution", "scripts.verify_orchestration_execution"),
    ("resource_governance", "scripts.verify_resource_governance"),
    ("persistence_recovery", "scripts.verify_persistence_recovery"),
    ("live_character_state", "scripts.verify_live_character_state"),
    ("release_hygiene", "scripts.verify_release_hygiene"),
    ("standalone_readiness", "scripts.verify_standalone_readiness"),
)


def _heading(title: str) -> None:
    print()
    print("=" * 80)
    print(title)
    print("=" * 80)


def _offline_environment() -> dict[str, str]:
    """Return a child-process environment that cannot enable live LLM pytest."""

    environment = os.environ.copy()
    environment.pop("MARY_RUN_LIVE_TESTS", None)
    environment.pop("MARY_RUN_OPENAI_TESTS", None)
    return environment


def discover_verifier_modules() -> tuple[str, ...]:
    """Return all verify_*.py modules currently present in scripts/."""

    return tuple(
        f"scripts.{path.stem}"
        for path in sorted((ROOT / "scripts").glob("verify_*.py"))
    )


def run_compile_check() -> bool:
    _heading("PYTHON COMPILE CHECK")
    ok = True
    for target in (ROOT / "mary", ROOT / "scripts"):
        ok = compileall.compile_dir(
            str(target),
            quiet=1,
            force=True,
        ) and ok

    ok = compileall.compile_file(
        str(ROOT / "main.py"),
        quiet=1,
        force=True,
    ) and ok

    print("PASS" if ok else "FAIL")
    return bool(ok)


def run_pytest() -> bool:
    """Run the canonical deterministic suite with live LLM testing disabled."""

    _heading("PYTEST - DETERMINISTIC / OFFLINE")
    completed = subprocess.run(
        [
            sys.executable,
            "-m",
            "pytest",
            "tests",
            "-q",
        ],
        cwd=ROOT,
        env=_offline_environment(),
        check=False,
    )
    return completed.returncode == 0


def run_diagnostics() -> bool:
    _heading("SYSTEM DIAGNOSTICS")
    mary = Mary()
    diagnostics = MaryDiagnostics(mary)
    print(diagnostics.report())
    summary = diagnostics.summary()
    return bool(
        summary.get("healthy")
        and summary.get("failed") == 0
    )


def run_verifier(name: str, module: str) -> bool:
    """Run one registered deterministic milestone verifier in-process."""

    _heading(f"MILESTONE VERIFIER - {name.replace('_', ' ').upper()}")
    original_argv = sys.argv[:]
    try:
        # Some standalone verifiers define their own argparse options. They
        # must not inherit release-runner flags such as --offline.
        sys.argv = [module]
        verifier = importlib.import_module(module)
        result = verifier.main()
    except SystemExit as exc:
        code = exc.code
        return code is None or code == 0
    except Exception as exc:
        print(f"FAIL: {type(exc).__name__}: {exc}")
        return False
    finally:
        sys.argv = original_argv

    if result is None:
        return True
    if isinstance(result, int):
        return result == 0
    return bool(result)


def run_local_safety_smoke() -> bool:
    _heading("LOCAL TOOL SAFETY SMOKE")

    with tempfile.TemporaryDirectory(prefix="maryv2_verify_") as directory:
        root = Path(directory)
        manager = ToolManager(workspace_root=root)

        # Workspace escape must fail.
        escape = manager.registry.execute_validated(
            "filesystem_read",
            {"path": "../outside.txt"},
        )
        if escape.success:
            print("FAIL: workspace escape unexpectedly succeeded")
            return False
        print("PASS: workspace escape blocked")

        # Static code analysis must not execute the source file.
        source = root / "static_only.py"
        marker = root / "SHOULD_NOT_EXIST.txt"
        source.write_text(
            "from pathlib import Path\n"
            "Path('SHOULD_NOT_EXIST.txt').write_text('executed')\n\n"
            "def hello():\n"
            "    return 'hello'\n",
            encoding="utf-8",
        )
        analysis = manager.registry.execute_validated(
            "code_analyze",
            {"path": "static_only.py"},
        )
        if not analysis.success or marker.exists():
            print("FAIL: static analysis executed code or failed")
            return False
        print("PASS: static code analysis did not execute source")

        # Mutating filesystem request must not run before approval.
        request = manager.request(
            "filesystem_write",
            {
                "path": "approval_test.txt",
                "content": "approved",
                "overwrite": False,
            },
            reason="release verification",
        )
        target = root / "approval_test.txt"
        if request.status != "pending" or target.exists():
            print("FAIL: write occurred before approval")
            return False
        print("PASS: write remained pending before approval")

        token = manager.approve(
            request.request_id,
            reason="release verification",
        )
        if token is None:
            print("FAIL: approval token was not created")
            return False

        result = manager.execute_approved(request.request_id)
        if not result.success or target.read_text(encoding="utf-8") != "approved":
            print("FAIL: approved write did not execute correctly")
            return False
        print("PASS: exact approved write executed")

    return True


def run_live_llm() -> bool:
    """Run the one explicitly enabled real-provider conversation smoke test."""

    _heading("EXPLICIT LIVE LLM PIPELINE")
    print(
        "This check is running because --live-llm was supplied. "
        "It runs only the dedicated live conversation test."
    )

    environment = os.environ.copy()
    environment["MARY_RUN_LIVE_TESTS"] = "1"
    completed = subprocess.run(
        [
            sys.executable,
            "-m",
            "pytest",
            LIVE_LLM_TEST,
            "-q",
            "-s",
        ],
        cwd=ROOT,
        env=environment,
        check=False,
    )
    return completed.returncode == 0


def run_live_web() -> bool:
    _heading("EXPLICIT LIVE WEB + GROUNDED RESPONSE")
    print(
        "This check is running because --live-web was supplied. "
        "It performs one explicit public web search."
    )

    with tempfile.TemporaryDirectory(prefix="maryv2_live_") as directory:
        memory_path = Path(directory) / "memory.json"
        app = create_application(
            memory_path=memory_path,
            auto_save=False,
            load_memory=False,
        )
        result = app.run(
            "search the web for the latest Python news"
        )

        if not result.success:
            print(f"FAIL: {result.error}")
            return False

        output = str(result.output or "")
        print(output)
        if not output.strip():
            print("FAIL: live research returned an empty response")
            return False
        if "Sources:" not in output:
            print("FAIL: live research response did not include Sources")
            return False

        print("PASS: live research returned a sourced response")
        return True


def main() -> int:
    parser = argparse.ArgumentParser(
        description="Run the canonical MaryV2 release verification gate."
    )
    parser.add_argument(
        "--offline",
        action="store_true",
        help=(
            "Run only the deterministic/offline release gate. This is already "
            "the default and is provided for explicitness."
        ),
    )
    parser.add_argument(
        "--live-llm",
        action="store_true",
        help=(
            "After the offline gate, intentionally run the dedicated real LLM "
            "conversation smoke test."
        ),
    )
    parser.add_argument(
        "--live-web",
        action="store_true",
        help=(
            "After the offline gate, intentionally perform one public web "
            "research request through Mary."
        ),
    )
    args = parser.parse_args()

    if args.offline and (args.live_llm or args.live_web):
        parser.error("--offline cannot be combined with --live-llm or --live-web")

    checks: list[tuple[str, bool]] = [
        ("compile", run_compile_check()),
        ("pytest", run_pytest()),
        ("diagnostics", run_diagnostics()),
    ]

    for name, module in OFFLINE_VERIFIERS:
        checks.append((name, run_verifier(name, module)))

    checks.append(("local_safety", run_local_safety_smoke()))

    if args.live_llm:
        checks.append(("live_llm", run_live_llm()))

    if args.live_web:
        checks.append(("live_web", run_live_web()))

    _heading("MARYV2 RELEASE VERIFICATION SUMMARY")
    for name, passed in checks:
        print(f"{'PASS' if passed else 'FAIL'}  {name}")

    failed = [name for name, passed in checks if not passed]
    if failed:
        print()
        print("Release verification FAILED:", ", ".join(failed))
        return 1

    print()
    if args.live_llm or args.live_web:
        print("Release verification PASSED, including requested live checks.")
    else:
        print("Release verification PASSED (deterministic/offline gate).")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
