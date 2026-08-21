"""Static release-hygiene checks for a private MaryV2 working tree.

A developer's real working tree may contain a local ``.env``. Release hygiene
therefore verifies that the file is ignored/excluded rather than requiring it
to be deleted. The file itself is never opened or scanned.

The scan intentionally ignores local dependency/runtime trees such as .venv,
.venv-1, Replit .pythonlibs, node_modules, build/dist output, caches, and
Mary's private data directory.

Example environment templates are scanned, but obvious placeholders such as
``your_provider_key_here`` are allowed.
"""
from __future__ import annotations

import re
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]

TEXT_SUFFIXES = {
    ".py",
    ".js",
    ".jsx",
    ".ts",
    ".tsx",
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

# Strong provider-shaped secrets. These remain suspicious anywhere in scanned
# project source, even if they are not assigned to a variable.
RAW_SECRET_PATTERNS = (
    re.compile(r"sk-proj-[A-Za-z0-9_-]{20,}"),
    re.compile(r"sk-[A-Za-z0-9_-]{32,}"),
)

# Only inspect literal assignments on a single line. This intentionally avoids
# treating normal code such as ``token = request.approval_token`` as a secret.
QUOTED_SECRET_ASSIGNMENT = re.compile(
    r"""(?ix)
    \b
    [A-Za-z0-9_$-]*
    (?:api[_-]?key|secret|token)
    [A-Za-z0-9_$-]*
    \s*=\s*
    ["']
    (?P<value>[^"'\r\n]+)
    ["']
    """
)

ENV_ASSIGNMENT = re.compile(
    r"""(?x)
    ^
    \s*
    (?P<name>[A-Za-z_][A-Za-z0-9_]*)
    \s*=\s*
    (?P<value>.*?)
    \s*
    $
    """
)

EXACT_SKIP_PARTS = {
    ".git",
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

# These files intentionally contain fake secret-shaped strings/patterns in
# order to test the hygiene scanner itself. They are not release credentials.
SELF_TEST_EXEMPTIONS = {
    Path("tests/scripts/test_release_hygiene.py"),
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

PLACEHOLDER_EXACT = {
    "",
    "none",
    "null",
    "unset",
    "disabled",
    "off",
}


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


def _is_dependency_or_runtime_part(part: str) -> bool:
    lowered = str(part or "").strip().lower()

    if lowered in EXACT_SKIP_PARTS:
        return True

    # Windows/Replit/IDE-created environment variants:
    # .venv, .venv-1, .venv311, venv, venv-2, etc.
    if lowered == ".venv" or lowered.startswith(".venv-"):
        return True
    if lowered == "venv" or lowered.startswith("venv-"):
        return True

    return False


def _is_placeholder_value(value: str) -> bool:
    normalized = str(value or "").strip().strip("\"'").lower()

    if normalized in PLACEHOLDER_EXACT:
        return True

    if normalized.startswith(PLACEHOLDER_PREFIXES):
        return True

    if normalized.endswith(("_here", "-here")):
        return True

    return False


def _looks_like_secret_name(name: str) -> bool:
    normalized = str(name or "").strip().lower().replace("-", "_")
    return any(
        marker in normalized
        for marker in ("api_key", "apikey", "secret", "token")
    )


def _contains_possible_secret(text: str, *, env_template: bool = False) -> bool:
    # A real provider-shaped raw key is suspicious anywhere.
    if any(pattern.search(text) for pattern in RAW_SECRET_PATTERNS):
        return True

    # In Python/JS/etc., only literal string assignments are considered generic
    # secret evidence. Normal object/attribute assignments are not.
    for line in text.splitlines():
        match = QUOTED_SECRET_ASSIGNMENT.search(line)
        if match and not _is_placeholder_value(match.group("value")):
            return True

    # Environment templates commonly use unquoted KEY=value assignments.
    if env_template:
        for raw_line in text.splitlines():
            line = raw_line.strip()
            if not line or line.startswith("#"):
                continue

            match = ENV_ASSIGNMENT.match(line)
            if match is None:
                continue

            name = match.group("name")
            value = match.group("value")

            if not _looks_like_secret_name(name):
                continue

            if not _is_placeholder_value(value):
                return True

    return False


def _is_scannable_text(path: Path) -> bool:
    if path.name in {".env.example", "example.env.example"}:
        return True
    return path.suffix.lower() in TEXT_SUFFIXES


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
        if not path.is_file():
            continue

        try:
            relative = path.relative_to(ROOT)
        except ValueError:
            continue

        if any(_is_dependency_or_runtime_part(part) for part in relative.parts):
            continue

        if relative in SELF_TEST_EXEMPTIONS:
            continue

        # Never inspect private local environment files. Their contract is
        # exclusion from source/package output, not absence from a developer PC.
        if _is_local_secret_file(path):
            continue

        if not _is_scannable_text(path):
            continue

        try:
            text = path.read_text(encoding="utf-8", errors="ignore")
        except OSError:
            continue

        env_template = path.name in {".env.example", "example.env.example"}

        if _contains_possible_secret(text, env_template=env_template):
            problems.append(f"possible secret in {relative}")

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
