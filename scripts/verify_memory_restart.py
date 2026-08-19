"""MaryV2 true cross-process memory persistence verification.

Run from the repository root with::

    python -m scripts.verify_memory_restart

The parent process launches two completely separate Python interpreters. The
first writes an explicit episodic memory through Mary's canonical application
runtime; the second starts a new Mary application, reloads the same memory file,
and recalls it. A temporary probe file is used so the verification never
pollutes Mary's real ``data/memory/memory.json``.
"""

from __future__ import annotations

import argparse
import subprocess
import sys
import tempfile
from pathlib import Path

from mary.runtime.application import create_application

PROBE_CONTENT = "the persistence restart probe phrase is cobalt lantern"
PROBE_QUERY = "what do you remember about persistence restart probe phrase?"
EXPECTED_FRAGMENT = "cobalt lantern"


def _write_phase(memory_path: Path) -> int:
    app = create_application(
        memory_path=memory_path,
        auto_save=True,
        load_memory=True,
        name="memory_restart_write",
    )
    try:
        result = app.run(f"remember that {PROBE_CONTENT}")
        if not result.success:
            print(f"WRITE FAIL: {result.error}")
            return 2
        if not memory_path.exists():
            print("WRITE FAIL: memory file was not created")
            return 3
        print(f"WRITE PASS: {result.output}")
        return 0
    finally:
        app.close()


def _read_phase(memory_path: Path) -> int:
    app = create_application(
        memory_path=memory_path,
        auto_save=True,
        load_memory=True,
        name="memory_restart_read",
    )
    try:
        result = app.run(PROBE_QUERY)
        if not result.success:
            print(f"READ FAIL: {result.error}")
            return 4
        output = str(result.output or "")
        if EXPECTED_FRAGMENT not in output.lower():
            print(f"READ FAIL: expected {EXPECTED_FRAGMENT!r} in {output!r}")
            return 5
        print(f"READ PASS: {output}")
        return 0
    finally:
        app.close()


def _run_child(phase: str, memory_path: Path) -> subprocess.CompletedProcess[str]:
    command = [
        sys.executable,
        "-m",
        "scripts.verify_memory_restart",
        "--phase",
        phase,
        "--memory-path",
        str(memory_path),
    ]
    return subprocess.run(
        command,
        cwd=Path(__file__).resolve().parents[1],
        text=True,
        capture_output=True,
        check=False,
    )


def _parent_phase() -> int:
    print("=" * 72)
    print("MARY V2 CROSS-PROCESS MEMORY PERSISTENCE")
    print("=" * 72)

    with tempfile.TemporaryDirectory(prefix="maryv2-memory-restart-") as directory:
        memory_path = Path(directory) / "memory" / "memory.json"

        write = _run_child("write", memory_path)
        if write.stdout.strip():
            print(write.stdout.strip())
        if write.stderr.strip():
            print(write.stderr.strip())
        if write.returncode != 0:
            print("RESULT: FAIL (write process)")
            return write.returncode

        read = _run_child("read", memory_path)
        if read.stdout.strip():
            print(read.stdout.strip())
        if read.stderr.strip():
            print(read.stderr.strip())
        if read.returncode != 0:
            print("RESULT: FAIL (read process)")
            return read.returncode

        print("-" * 72)
        print("RESULT: PASS")
        print("A completely new Python process reloaded and recalled Mary's memory.")
        print("The probe used a temporary memory file; Mary's real memory was untouched.")
        return 0


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--phase", choices=("parent", "write", "read"), default="parent")
    parser.add_argument("--memory-path")
    args = parser.parse_args()

    if args.phase == "parent":
        return _parent_phase()

    if not args.memory_path:
        parser.error("--memory-path is required for child phases")

    memory_path = Path(args.memory_path)
    if args.phase == "write":
        return _write_phase(memory_path)
    return _read_phase(memory_path)


if __name__ == "__main__":
    raise SystemExit(main())
