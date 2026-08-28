"""Static release-hygiene checks for a private MaryV2 working tree."""
from __future__ import annotations

import re
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]

TEXT_SUFFIXES = {
    ".py", ".js", ".jsx", ".ts", ".tsx", ".html", ".css", ".md", ".txt",
    ".json", ".toml", ".yml", ".yaml", ".ps1", ".sh", ".example",
}

RAW_SECRET_PATTERNS = (
    re.compile(r"sk-proj-[A-Za-z0-9_-]{20,}"),
    re.compile(r"sk-[A-Za-z0-9_-]{32,}"),
)

QUOTED_SECRET_ASSIGNMENT = re.compile(
    r'''(?ix)\b[A-Za-z0-9_$-]*(?:api[_-]?key|secret|token)[A-Za-z0-9_$-]*\s*=\s*["'](?P<value>[^"'\r\n]+)["']'''
)

ENV_ASSIGNMENT = re.compile(
    r"^(?P<name>[A-Za-z_][A-Za-z0-9_]*)\s*=\s*(?P<value>.*?)\s*$"
)

EXACT_SKIP_PARTS = {
    ".git", ".pythonlibs", "__pypackages__", "node_modules", "__pycache__",
    ".pytest_cache", ".mypy_cache", ".ruff_cache", ".cache", "data", "dist", "build",
}

LOCAL_SECRET_NAMES = {".env", ".env.bak", ".env.before_cleanup.bak"}
SELF_TEST_EXEMPTIONS = {Path("tests/scripts/test_release_hygiene.py")}

PLACEHOLDER_PREFIXES = (
    "your_", "your-", "example_", "example-", "sample_", "sample-", "replace_", "replace-",
    "changeme", "change_me", "change-me", "placeholder", "dummy_", "dummy-", "test_", "test-",
    "fake_", "fake-", "mock_", "mock-", "secret-test-", "tvly-test-", "<", "${",
)
PLACEHOLDER_EXACT = {"", "none", "null", "unset", "disabled", "off", "secret", "test-key", "fake-key", "dummy-key", "use-a-long-random-secret"}


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
    return name in LOCAL_SECRET_NAMES or (name.startswith(".env.") and name != ".env.example")


def _is_dependency_or_runtime_part(part: str) -> bool:
    lowered = str(part or "").strip().lower()
    if lowered in EXACT_SKIP_PARTS:
        return True
    return lowered == ".venv" or lowered.startswith(".venv-") or lowered.startswith(".venv_") or lowered == "venv" or lowered.startswith("venv-") or lowered.startswith("venv_")


def _is_placeholder_value(value: str) -> bool:
    normalized = str(value or "").strip().strip('"\'').lower()
    if normalized in PLACEHOLDER_EXACT:
        return True
    if normalized.startswith(PLACEHOLDER_PREFIXES):
        return True
    if normalized.endswith(("_here", "-here", "-test-key", "_test_key")):
        return True
    return False


def _looks_like_secret_name(name: str) -> bool:
    normalized = str(name or "").strip().lower().replace("-", "_")
    return any(marker in normalized for marker in ("api_key", "apikey", "secret", "token"))


def _contains_possible_secret(text: str, *, env_template: bool = False) -> bool:
    if any(pattern.search(text) for pattern in RAW_SECRET_PATTERNS):
        return True
    for line in text.splitlines():
        match = QUOTED_SECRET_ASSIGNMENT.search(line)
        if match and not _is_placeholder_value(match.group("value")):
            return True
    if env_template:
        for raw_line in text.splitlines():
            line = raw_line.strip()
            if not line or line.startswith("#"):
                continue
            match = ENV_ASSIGNMENT.match(line)
            if match is None:
                continue
            if _looks_like_secret_name(match.group("name")) and not _is_placeholder_value(match.group("value")):
                return True
    return False


def _is_scannable_text(path: Path) -> bool:
    return path.name in {".env.example", "example.env.example"} or path.suffix.lower() in TEXT_SUFFIXES


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
        if _is_local_secret_file(path) or not _is_scannable_text(path):
            continue
        try:
            text = path.read_text(encoding="utf-8", errors="ignore")
        except OSError:
            continue
        if _contains_possible_secret(text, env_template=path.name in {".env.example", "example.env.example"}):
            problems.append(f"possible secret in {relative}")

    if problems:
        for problem in problems:
            print(f"FAIL  {problem}")
        return 1

    print("PASS  local .env may exist in the working tree and is ignored" if local_env.exists() else "PASS  no local .env is present in this source snapshot")
    print("PASS  no obvious raw API-key pattern appears in releasable source")
    print("PASS  private env/runtime/build/cache paths are excluded from release scan scope")
    print("=" * 72)
    print("RELEASE HYGIENE VERIFIED")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
