"""
MaryV2 release verification runner.

This script is intentionally explicit about live external access.

Default behavior:
    - compile Mary/source files
    - run the full pytest suite (including the configured live LLM test)
    - run system diagnostics
    - run local safety smoke checks

Use --offline to skip the live LLM pytest module.
Use --live-web to additionally perform one explicit live Tavily/Mary research
request.  The live-web check is never run unless the creator supplies that flag.
"""

from __future__ import annotations

import argparse
import compileall
import subprocess
import sys
import tempfile
from pathlib import Path

from mary.core.diagnostics import MaryDiagnostics
from mary.core.mary import Mary
from mary.runtime.application import create_application
from mary.tools.manager import ToolManager


ROOT = Path(__file__).resolve().parents[1]


def _heading(title: str) -> None:
    print()
    print("=" * 80)
    print(title)
    print("=" * 80)


def run_compile_check() -> bool:
    _heading("1. PYTHON COMPILE CHECK")
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


def run_pytest(*, offline: bool) -> bool:
    _heading("2. PYTEST")
    command = [
        sys.executable,
        "-m",
        "pytest",
        "tests",
        "-q",
    ]
    if offline:
        command.extend([
            "--ignore=tests/conversation/test_live_pipeline.py",
        ])

    completed = subprocess.run(
        command,
        cwd=ROOT,
        check=False,
    )
    return completed.returncode == 0


def run_diagnostics() -> bool:
    _heading("3. SYSTEM DIAGNOSTICS")
    mary = Mary()
    diagnostics = MaryDiagnostics(mary)
    print(diagnostics.report())
    summary = diagnostics.summary()
    return bool(
        summary.get("healthy")
        and summary.get("failed") == 0
    )


def run_resilience_install_check() -> bool:
    _heading("4. PROVIDER RESILIENCE CHECK")
    completed = subprocess.run(
        [sys.executable, "-m", "scripts.verify_resilience_install"],
        cwd=ROOT,
        check=False,
    )
    return completed.returncode == 0


def run_local_safety_smoke() -> bool:
    _heading("5. LOCAL TOOL SAFETY SMOKE")

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


def run_live_web() -> bool:
    _heading("6. EXPLICIT LIVE WEB + GROUNDED RESPONSE")
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
        try:
            result = app.run(
                "search the web for the latest Python news"
            )
        finally:
            # auto_save=False means close() may return False with a temp path
            # that has not been saved. That is not relevant to this smoke test.
            pass

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
        description="Run MaryV2 release verification checks."
    )
    parser.add_argument(
        "--offline",
        action="store_true",
        help="Skip the configured live LLM pytest module.",
    )
    parser.add_argument(
        "--live-web",
        action="store_true",
        help=(
            "Perform one explicit live web search through Mary after the "
            "offline/system checks."
        ),
    )
    args = parser.parse_args()

    checks = [
        ("compile", run_compile_check()),
        ("pytest", run_pytest(offline=args.offline)),
        ("diagnostics", run_diagnostics()),
        ("resilience", run_resilience_install_check()),
        ("local_safety", run_local_safety_smoke()),
    ]

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
    print("Release verification PASSED.")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
