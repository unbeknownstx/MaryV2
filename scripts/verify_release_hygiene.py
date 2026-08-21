"""Static release-hygiene checks for a private MaryV2 working tree.

A developer's real working tree is expected to contain a local ``.env``.
Release hygiene therefore verifies that the file is ignored/excluded rather
than requiring it to be deleted. The file itself is never opened or scanned.

The scan is intentionally limited to MaryV2 release source. Host-managed
dependency trees such as Replit's ``.pythonlibs`` are not project source.
Example environment templates may contain obvious placeholder values such as
``your_provider_key_here``; those are not treated as leaked credentials.
"""
from __future__ import annotations

import re
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]

TEXT_SUFFIXES = {
    ".py",
    ".js",
    ".html",
    ".css",
    ".md",
    ".txt",
    ".json",
    ".toml",
    ".yml",
    ".yaml",
    ".ps1",
    ".sh",
    ".example",
}

RAW_SECRET_PATTERNS = [
    re.compile(r"sk-proj-[A-Za-z0-9_-]{20,}"),
    re.compile(r"sk-[A-Za-z0-9_-]{32,}"),
]

SECRET_ASSIGNMENT_PATTERN = re.compile(
    r"""(?ix)
    (?:api[_-]?key|secret|token)
    \s*=\s*
    ["']?
    (?P<value>[A-Za-z0-9_./:+\-{}$<>]{20,})
    """
)

SKIP_PARTS = {
    ".git",
    ".venv",
    "venv",
    ".pythonlibs",
    "__pypackages__",
    "node_modules",
    "__pycache__",
    ".pytest_cache",
    ".mypy_cache",
    ".ruff_cache",
    ".cache",
    "data",
    "dist",
    "build",
}

LOCAL_SECRET_NAMES = {
    ".env",
    ".env.bak",
    ".env.before_cleanup.bak",
}

PLACEHOLDER_PREFIXES = (
    "your_",
    "example_",
    "sample_",
    "replace_",
    "changeme",
    "change_me",
    "placeholder",
    "dummy_",
    "test_",
    "<",
    "${",
)


def _gitignore_rules() -> set[str]:
    path = ROOT / ".gitignore"
    if not path.exists():
        return set()

    rules: set[str] = set()
    for raw in path.read_text(encoding="utf-8", errors="ignore").splitlines():
        line = raw.strip()
        if not line or line.startswith("#") or line.startswith("!"):
            continue
        rules.add(line.rstrip("/"))
    return rules


def _is_local_secret_file(path: Path) -> bool:
    name = path.name
    return name in LOCAL_SECRET_NAMES or (
        name.startswith(".env.") and name != ".env.example"
    )


def _is_placeholder_value(value: str) -> bool:
    normalized = str(value or "").strip().strip("\"'").lower()
    if not normalized:
        return True

    if normalized in {
        "none",
        "null",
        "unset",
        "disabled",
        "off",
    }:
        return True

    return normalized.startswith(PLACEHOLDER_PREFIXES) or normalized.endswith(
        ("_here", "-here")
    )


def _contains_possible_secret(text: str) -> bool:
    # Provider-shaped raw keys are always suspicious, even inside examples.
    if any(pattern.search(text) for pattern in RAW_SECRET_PATTERNS):
        return True

    # Generic API_KEY/TOKEN/SECRET assignments are suspicious only when the
    # assigned value is not clearly an example/template placeholder.
    for match in SECRET_ASSIGNMENT_PATTERN.finditer(text):
        if not _is_placeholder_value(match.group("value")):
            return True

    return False


def main() -> int:
    print("=" * 72)
    print("MARYV2 RELEASE HYGIENE")
    print("=" * 72)

    problems: list[str] = []
    ignore_rules = _gitignore_rules()

    local_env = ROOT / ".env"
    if local_env.exists() and ".env" not in ignore_rules:
        problems.append("local .env exists but .gitignore does not exclude it")

    for path in ROOT.rglob("*"):
        if not path.is_file() or any(part in SKIP_PARTS for part in path.parts):
            continue

        # Never inspect private local environment files. Their contract is
        # exclusion from source/package output, not absence from a developer PC.
        if _is_local_secret_file(path):
            continue

        if path.suffix.lower() not in TEXT_SUFFIXES and path.name != ".env.example":
            continue

        try:
            text = path.read_text(encoding="utf-8", errors="ignore")
        except OSError:
            continue

        if _contains_possible_secret(text):
            problems.append(f"possible secret in {path.relative_to(ROOT)}")

    if problems:
        for problem in problems:
            print(f"FAIL  {problem}")
        return 1

    if local_env.exists():
        print("PASS  local .env may exist in the working tree and is ignored")
    else:
        print("PASS  no local .env is present in this source snapshot")

    print("PASS  no obvious raw API-key pattern appears in releasable source")
    print("PASS  private env/runtime/build/cache paths are excluded from release scan scope")
    print("=" * 72)
    print("RELEASE HYGIENE VERIFIED")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
