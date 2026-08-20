"""Static release-hygiene checks for a private MaryV2 source tree."""
from __future__ import annotations

import re
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
TEXT_SUFFIXES = {".py", ".js", ".html", ".css", ".md", ".txt", ".json", ".toml", ".yml", ".yaml", ".ps1", ".example"}
SECRET_PATTERNS = [
    re.compile(r"sk-proj-[A-Za-z0-9_-]{20,}"),
    re.compile(r"sk-[A-Za-z0-9_-]{32,}"),
    re.compile(r"(?i)(?:api[_-]?key|secret|token)\s*=\s*['\"]?[A-Za-z0-9_-]{32,}"),
]
SKIP_PARTS = {".git", ".venv", "node_modules", "__pycache__", "data", "dist", "build"}


def main() -> int:
    print("=" * 72)
    print("MARYV2 RELEASE HYGIENE")
    print("=" * 72)
    problems: list[str] = []
    for path in ROOT.rglob("*"):
        if not path.is_file() or any(part in SKIP_PARTS for part in path.parts):
            continue
        if path.name == ".env":
            problems.append("source tree contains .env")
            continue
        if path.suffix.lower() not in TEXT_SUFFIXES and path.name != ".env.example":
            continue
        try:
            text = path.read_text(encoding="utf-8", errors="ignore")
        except OSError:
            continue
        for pattern in SECRET_PATTERNS:
            if pattern.search(text):
                problems.append(f"possible secret in {path.relative_to(ROOT)}")
                break
    if problems:
        for problem in problems:
            print(f"FAIL  {problem}")
        return 1
    print("PASS  no .env file is part of the releasable source tree")
    print("PASS  no obvious raw API-key pattern appears in releasable source")
    print("PASS  runtime data/build/cache directories are excluded from scan scope")
    print("=" * 72)
    print("RELEASE HYGIENE VERIFIED")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
