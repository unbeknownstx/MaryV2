$ErrorActionPreference = "Stop"

Write-Host "MARYV2 13.1.1 MEMORY INTEGRITY HOTFIX V2"
Write-Host "========================================="

$root = Get-Location
$maryFile = Join-Path $root "mary\core\mary.py"
$testFile = Join-Path $root "tests\cognition\test_creator_directives.py"
$memoryFile = Join-Path $root "data\memory\memory.json"

foreach ($p in @($maryFile, $testFile)) {
    if (-not (Test-Path $p)) {
        throw "Required file not found: $p"
    }
}

$stamp = Get-Date -Format "yyyyMMdd_HHmmss"

Copy-Item $maryFile "$maryFile.pre_memory_integrity_v2_$stamp" -Force
Copy-Item $testFile "$testFile.pre_memory_integrity_v2_$stamp" -Force

if (Test-Path $memoryFile) {
    Copy-Item $memoryFile "$memoryFile.pre_memory_integrity_v2_$stamp" -Force
}

@'
from pathlib import Path
import json
import re

mary_path = Path("mary/core/mary.py")
test_path = Path("tests/cognition/test_creator_directives.py")
memory_path = Path("data/memory/memory.json")

# 1. Harden canonical memory write boundary.
source = mary_path.read_text(encoding="utf-8")
start = source.index("    def _handle_memory_store(")
end = source.index("\n    def ", start + 1)
method = source[start:end]

anchor = '''        if not content:

            return (
                "What would you like me to remember?"
            )

        memory = self.remember(
'''

replacement = '''        if not content:

            return (
                "What would you like me to remember?"
            )

        # 13.1.1 memory-integrity guard.
        # Repair the known legacy boundary-collapse artifact at the final
        # canonical write boundary so it can never persist again.
        content = re.sub(
            r"\\bmemoryto\\b",
            "memory to",
            content,
            flags=re.IGNORECASE,
        )

        memory = self.remember(
'''

if "13.1.1 memory-integrity guard." not in method:
    if anchor not in method:
        raise RuntimeError(
            "Could not find the canonical memory-store insertion point."
        )
    method = method.replace(anchor, replacement, 1)

mary_path.write_text(
    source[:start] + method + source[end:],
    encoding="utf-8",
)

# 2. Add isolated regression coverage.
test_source = test_path.read_text(encoding="utf-8")
test_name = "test_memory_store_repairs_legacy_memoryto_boundary_artifact"

if test_name not in test_source:
    addition = r'''


def test_memory_store_repairs_legacy_memoryto_boundary_artifact(
    tmp_path,
    monkeypatch,
):
    mary, provider, app = _rate_limited_app(
        tmp_path,
        monkeypatch,
    )

    text = (
        "me and you are all in mary promise me that. "
        "an i will remember this as a core memoryto me. "
        "you can have this core memory remember this. "
        "i will support you always"
    )

    before = len(mary.memory.episodic.all())
    result = app.run(text)
    memories = mary.memory.episodic.all()

    assert result.success is True
    assert provider.calls == 0
    assert len(memories) == before + 1
    assert "memoryto" not in memories[-1].content
    assert "core memory to me" in memories[-1].content
    assert result.output == "Got it. I'll remember this."
'''
    test_path.write_text(test_source + addition, encoding="utf-8")

for path in (mary_path, test_path):
    compile(path.read_text(encoding="utf-8"), str(path), "exec")

# 3. Controlled one-time repair of the duplicate live records.
repair_report = {
    "memory_file_present": memory_path.exists(),
    "matched": 0,
    "repaired": 0,
    "duplicates_removed": 0,
}

if memory_path.exists():
    payload = json.loads(memory_path.read_text(encoding="utf-8"))
    episodic = payload.get("episodic", [])

    if not isinstance(episodic, list):
        raise RuntimeError("memory.json episodic field is not a list.")

    target_prefix = (
        "me and you are all in mary promise me that. "
        "an i will remember this as a core memory"
    )

    matches = []

    for index, item in enumerate(episodic):
        if not isinstance(item, dict):
            continue

        content = str(item.get("content", ""))
        metadata = item.get("metadata") or {}

        if (
            content.lower().startswith(target_prefix)
            and "i will support you always" in content.lower()
            and metadata.get("owner") == "creator"
            and metadata.get("speaker") == "Unbe"
            and item.get("source") == "interaction"
            and item.get("event_type") == "user_statement"
        ):
            matches.append((index, item))

    repair_report["matched"] = len(matches)

    if matches:
        keep_index, keep_item = matches[0]

        clean_content = re.sub(
            r"\bmemoryto\b",
            "memory to",
            str(keep_item.get("content", "")),
            flags=re.IGNORECASE,
        )

        if clean_content != keep_item.get("content"):
            keep_item["content"] = clean_content
            repair_report["repaired"] += 1

        duplicate_indices = {
            index
            for index, _item in matches[1:]
        }

        if duplicate_indices:
            episodic = [
                item
                for index, item in enumerate(episodic)
                if index not in duplicate_indices
            ]
            repair_report["duplicates_removed"] = len(duplicate_indices)

        payload["episodic"] = episodic
        memory_path.write_text(
            json.dumps(payload, indent=2, ensure_ascii=False) + "\n",
            encoding="utf-8",
        )

print("PATCH: PASS")
print("LIVE MEMORY REPAIR:", json.dumps(repair_report))
'@ | python -

Write-Host ""
Write-Host "Running targeted cognition tests..."
python -m pytest tests\cognition\test_creator_directives.py -q

if ($LASTEXITCODE -ne 0) {
    throw "Targeted cognition tests failed."
}

Write-Host ""
Write-Host "MARYV2 MEMORY INTEGRITY HOTFIX V2 VERIFIED"
Write-Host "Backups use suffix: .pre_memory_integrity_v2_$stamp"
