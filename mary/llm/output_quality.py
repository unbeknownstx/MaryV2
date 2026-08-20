"""Provider-output quality checks used before an LLM response reaches Mary.

This layer catches obvious transport/generation corruption while preserving
legitimate multilingual tasks.  It is intentionally small and deterministic;
it does not judge style or factual correctness.
"""

from __future__ import annotations

from dataclasses import dataclass
import re
import unicodedata
from typing import Iterable

from .interface import LLMMessage


_LANGUAGE_REQUEST_MARKERS = (
    "translate", "translation", "in japanese", "in korean", "in chinese",
    "in mandarin", "in arabic", "in russian", "in hindi", "in thai",
    "japanese word", "korean word", "chinese word", "write in japanese",
    "write in korean", "write in chinese", "what does", "how do you say",
)

_UNEXPECTED_SCRIPT_NAMES = (
    "CJK UNIFIED",
    "CJK COMPATIBILITY",
    "HANGUL",
    "HIRAGANA",
    "KATAKANA",
    "BOPOMOFO",
    "THAI",
    "ARABIC",
    "CYRILLIC",
    "HEBREW",
    "DEVANAGARI",
)


@dataclass(frozen=True)
class OutputQualityIssue:
    code: str
    description: str


def _message_text(messages: Iterable[LLMMessage]) -> str:
    return "\n".join(str(getattr(item, "content", "") or "") for item in messages)


def _script_counts(text: str) -> dict[str, int]:
    counts: dict[str, int] = {}
    for char in str(text or ""):
        if char.isspace() or char.isascii():
            continue
        try:
            name = unicodedata.name(char)
        except ValueError:
            continue
        for marker in _UNEXPECTED_SCRIPT_NAMES:
            if marker in name:
                counts[marker] = counts.get(marker, 0) + 1
                break
    return counts


def inspect_output_quality(
    content: str,
    messages: Iterable[LLMMessage],
) -> OutputQualityIssue | None:
    """Return an issue when output is obviously corrupted for the current task."""

    text = str(content or "")
    if not text.strip():
        return OutputQualityIssue("empty_output", "Provider returned empty output.")

    if "\ufffd" in text or "\x00" in text:
        return OutputQualityIssue(
            "encoding_corruption",
            "Provider output contains replacement/null characters.",
        )

    prompt_text = _message_text(messages)
    lowered_prompt = prompt_text.lower()
    if any(marker in lowered_prompt for marker in _LANGUAGE_REQUEST_MARKERS):
        return None

    prompt_scripts = _script_counts(prompt_text)
    response_scripts = _script_counts(text)
    foreign_count = sum(
        count
        for script, count in response_scripts.items()
        if prompt_scripts.get(script, 0) == 0
    )

    # One isolated glyph can be a harmless name/symbol. Multiple characters
    # from an unrequested script in an English/Latin interaction strongly match
    # the corrupted-token failure observed during real Mary acceptance testing.
    if foreign_count >= 2:
        details = ", ".join(
            f"{name}={count}"
            for name, count in response_scripts.items()
            if prompt_scripts.get(name, 0) == 0
        )
        return OutputQualityIssue(
            "unexpected_script",
            "Provider output contains unrequested script characters: " + details,
        )

    # Catch short repeated corruption seams such as ``x/癞넴`` even when only
    # one foreign glyph survives tokenization.
    if foreign_count and re.search(r"[/\\][^\x00-\x7F]{1,6}", text):
        return OutputQualityIssue(
            "mixed_script_fragment",
            "Provider output contains an unexpected mixed-script fragment.",
        )

    return None
