"""Keep the canonical mobile_web shell and native iOS www bundle identical.

Usage:
    python -m scripts.sync_mobile_web --check
    python -m scripts.sync_mobile_web --sync

The browser/PWA source of truth is ``mobile_web``.  The native Xcode app embeds
an exact generated copy under ``mobile_native/MaryMobile/www``.
"""
from __future__ import annotations

import argparse
import hashlib
from pathlib import Path
import shutil
import sys

ROOT = Path(__file__).resolve().parents[1]
SOURCE = ROOT / "mobile_web"
TARGET = ROOT / "mobile_native" / "MaryMobile" / "www"
IGNORED = {".DS_Store"}


def _files(root: Path) -> dict[str, str]:
    result: dict[str, str] = {}
    if not root.exists():
        return result
    for path in sorted(root.rglob("*")):
        if not path.is_file() or path.name in IGNORED:
            continue
        rel = path.relative_to(root).as_posix()
        result[rel] = hashlib.sha256(path.read_bytes()).hexdigest()
    return result


def drift() -> dict[str, list[str]]:
    source = _files(SOURCE)
    target = _files(TARGET)
    return {
        "missing": sorted(set(source) - set(target)),
        "extra": sorted(set(target) - set(source)),
        "changed": sorted(name for name in set(source) & set(target) if source[name] != target[name]),
    }


def in_sync() -> bool:
    report = drift()
    return not any(report.values())


def sync() -> None:
    if not SOURCE.is_dir():
        raise RuntimeError(f"Canonical mobile source is missing: {SOURCE}")
    if TARGET.exists():
        shutil.rmtree(TARGET)
    shutil.copytree(SOURCE, TARGET)


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    group = parser.add_mutually_exclusive_group(required=True)
    group.add_argument("--check", action="store_true", help="fail when native www differs from mobile_web")
    group.add_argument("--sync", action="store_true", help="replace native www with mobile_web")
    args = parser.parse_args(argv)

    if args.sync:
        sync()

    report = drift()
    ok = not any(report.values())
    if ok:
        print("Mary mobile bundles are synchronized.")
        return 0

    print("Mary mobile bundle drift detected:")
    for key in ("missing", "extra", "changed"):
        if report[key]:
            print(f"  {key}: {', '.join(report[key])}")
    if args.sync:
        print("Sync did not converge.")
    else:
        print("Run: python -m scripts.sync_mobile_web --sync")
    return 1


if __name__ == "__main__":
    raise SystemExit(main())
