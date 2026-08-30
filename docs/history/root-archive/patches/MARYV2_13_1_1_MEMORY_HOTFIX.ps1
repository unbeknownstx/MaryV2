$ErrorActionPreference = "Stop"

Write-Host "MARYV2 13.1.1 MEMORY HOTFIX"
Write-Host "============================"

$root = Get-Location
$orchestrator = Join-Path $root "mary\cognition\orchestrator.py"
$maryFile = Join-Path $root "mary\core\mary.py"
$testFile = Join-Path $root "tests\cognition\test_creator_directives.py"

foreach ($p in @($orchestrator, $maryFile, $testFile)) {
    if (-not (Test-Path $p)) {
        throw "Required file not found: $p"
    }
}

$stamp = Get-Date -Format "yyyyMMdd_HHmmss"

Copy-Item $orchestrator "$orchestrator.pre_memory_hotfix_$stamp" -Force
Copy-Item $maryFile "$maryFile.pre_memory_hotfix_$stamp" -Force
Copy-Item $testFile "$testFile.pre_memory_hotfix_$stamp" -Force

@'
from pathlib import Path
import re

orchestrator_path = Path("mary/cognition/orchestrator.py")
mary_path = Path("mary/core/mary.py")
test_path = Path("tests/cognition/test_creator_directives.py")

source = orchestrator_path.read_text(encoding="utf-8")
start = source.index("    def _detect_memory_store(")
end = source.index("\n    def ", start + 1)

new_method = r'''    def _detect_memory_store(
        self,
        *,
        text: str,
        lowered: str,
    ) -> Intent | None:
        # Detect explicit requests to store information in memory.
        # Mary only stores automatically when the creator clearly
        # authorizes persistence.

        explicit_payload_patterns = (
            r"\bremember\s+this\s*:\s*(.+)$",
            r"\bremember\s+the\s+following\s*:\s*(.+)$",
            r"\bi\s+want\s+you\s+to\s+remember\s+this\s*:\s*(.+)$",
            r"\bplease\s+remember\s+this\s*:\s*(.+)$",
        )

        for pattern in explicit_payload_patterns:
            match = re.search(
                pattern,
                text,
                flags=re.IGNORECASE | re.DOTALL,
            )
            if match is None:
                continue

            content = match.group(1).strip()
            if not content:
                continue

            return Intent(
                intent_type=IntentType.MEMORY_STORE,
                confidence=0.99,
                description=(
                    "Input explicitly requests that the following payload "
                    "be remembered."
                ),
                parameters={"content": content},
                source="basic_detector",
            )

        prefixes = (
            "remember that ",
            "remember ",
            "don't forget that ",
            "dont forget that ",
            "don't forget ",
            "dont forget ",
            "keep in mind that ",
            "keep in mind ",
            "i want you to remember that ",
            "i want you to remember ",
            "i need you to remember that ",
            "i need you to remember ",
            "please remember that ",
            "please remember ",
        )

        for prefix in prefixes:
            if not lowered.startswith(prefix):
                continue

            content = text[len(prefix):].strip()
            if not content:
                continue

            return Intent(
                intent_type=IntentType.MEMORY_STORE,
                confidence=0.95,
                description=(
                    "Input explicitly requests that information be remembered."
                ),
                parameters={"content": content},
                source="basic_detector",
            )

        embedded_authorization_patterns = (
            r"\byou\s+can\s+remember\s+this\b",
            r"\bi\s+(?:want|need)\s+you\s+to\s+remember\s+this\b",
            r"\bplease\s+remember\s+this\b",
            r"\bmake\s+this\s+(?:a\s+)?core\s+memory\b",
            r"\bkeep\s+this\s+(?:as\s+)?(?:a\s+)?core\s+memory\b",
            (
                r"\byou\s+can\s+have\s+this\s+"
                r"(?:as\s+)?(?:a\s+)?core\s+memory"
                r"(?:\s*,?\s*remember\s+this)?\b"
            ),
        )

        for pattern in embedded_authorization_patterns:
            match = re.search(
                pattern,
                text,
                flags=re.IGNORECASE | re.DOTALL,
            )
            if match is None:
                continue

            left = text[:match.start()].rstrip()
            right = text[match.end():].lstrip(" \t\r\n.,;:-")

            if left and right:
                content = f"{left} {right}"
            else:
                content = left or right

            content = re.sub(r"\s+", " ", content).strip()
            content = re.sub(r"\s+([,;:!?])", r"\1", content)
            content = re.sub(r"\.\s*\.", ".", content)
            content = content.strip(" \t\r\n,;:-")

            if not content:
                continue

            return Intent(
                intent_type=IntentType.MEMORY_STORE,
                confidence=0.98,
                description=(
                    "Input contains an explicit natural-language "
                    "authorization to remember the surrounding content."
                ),
                parameters={"content": content},
                source="basic_detector",
            )

        return None
'''

orchestrator_path.write_text(
    source[:start] + new_method + source[end:],
    encoding="utf-8",
)

source = mary_path.read_text(encoding="utf-8")
start = source.index("    def _handle_memory_store(")
end = source.index("\n    def ", start + 1)
method = source[start:end]

old = '''        rendered_content = (
            self._creator_to_second_person(
                content
            )
        )

        return (
            "Got it. I'll remember that "
            f"{rendered_content}."
        )
'''

new = '''        has_creator_first_person = bool(
            re.search(
                r"\\b(?:i|i'm|i've|i'll|i'd|me|my|mine|myself)\\b",
                content,
                flags=re.IGNORECASE,
            )
        )
        has_second_person = bool(
            re.search(
                r"\\b(?:you|you're|you've|you'll|you'd|your|yours|yourself)\\b",
                content,
                flags=re.IGNORECASE,
            )
        )

        if has_creator_first_person and has_second_person:
            return "Got it. I'll remember this."

        rendered_content = (
            self._creator_to_second_person(
                content
            )
        )

        return (
            "Got it. I'll remember that "
            f"{rendered_content}."
        )
'''

if old not in method:
    raise RuntimeError(
        "Could not find the expected memory confirmation block in mary/core/mary.py"
    )

method = method.replace(old, new, 1)
mary_path.write_text(
    source[:start] + method + source[end:],
    encoding="utf-8",
)

test_source = test_path.read_text(encoding="utf-8")
test_name = "test_embedded_natural_memory_authorization_preserves_content_and_confirmation"

if test_name not in test_source:
    addition = r'''


def test_embedded_natural_memory_authorization_preserves_content_and_confirmation(
    tmp_path,
    monkeypatch,
):
    mary, provider, app = _rate_limited_app(
        tmp_path,
        monkeypatch,
    )

    text = (
        "me and you are all in mary promise me that. "
        "an i will remember this as a core memory to me. "
        "you can have this core memory remember this. "
        "i will support you always"
    )

    intent = mary.cognition.detect_intent(text)

    assert intent.intent_type == IntentType.MEMORY_STORE
    assert intent.parameters["content"] == (
        "me and you are all in mary promise me that. "
        "an i will remember this as a core memory to me. "
        "i will support you always"
    )
    assert "memoryto" not in intent.parameters["content"]

    before = len(mary.memory.episodic.all())
    result = app.run(text)
    memories = mary.memory.episodic.all()

    assert result.success is True
    assert provider.calls == 0
    assert len(memories) == before + 1
    assert memories[-1].content == intent.parameters["content"]
    assert result.output == "Got it. I'll remember this."

    recall = mary.cognition.detect_intent(
        "do you remember this?"
    )
    assert recall.intent_type != IntentType.MEMORY_STORE

    ordinary = mary.cognition.detect_intent(
        "I remember this from before"
    )
    assert ordinary.intent_type != IntentType.MEMORY_STORE


def test_simple_memory_confirmation_still_uses_second_person(
    tmp_path,
    monkeypatch,
):
    mary, provider, app = _rate_limited_app(
        tmp_path,
        monkeypatch,
    )

    result = app.run(
        "remember that my favorite color is blue"
    )

    assert result.success is True
    assert provider.calls == 0
    assert "your favorite color is blue" in result.output.lower()
'''
    test_path.write_text(test_source + addition, encoding="utf-8")

for path in (orchestrator_path, mary_path, test_path):
    compile(path.read_text(encoding="utf-8"), str(path), "exec")

print("PATCH: PASS")
print("orchestrator:", orchestrator_path)
print("mary:", mary_path)
print("tests:", test_path)
'@ | python -

Write-Host ""
Write-Host "Running targeted tests..."
python -m pytest tests\cognition\test_creator_directives.py -q

if ($LASTEXITCODE -ne 0) {
    throw "Targeted cognition tests failed."
}

Write-Host ""
Write-Host "MARYV2 MEMORY HOTFIX VERIFIED"
Write-Host "Backups were created with suffix: .pre_memory_hotfix_$stamp"
