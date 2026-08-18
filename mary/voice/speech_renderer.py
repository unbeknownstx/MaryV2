"""Natural spoken-text rendering for MaryV2.

The renderer converts a canonical text response into a TTS-friendly variant
without changing the response displayed in the GUI. It is deliberately local
and deterministic: no provider, LLM, network request, memory mutation, or
reasoning step is involved.
"""

from __future__ import annotations

import re


class SpeechRenderer:
    """Render Mary's written response into a cleaner spoken form."""

    _FENCED_CODE_RE = re.compile(r"```[\s\S]*?```", re.MULTILINE)
    _MARKDOWN_LINK_RE = re.compile(r"\[([^\]]+)\]\((?:https?://|www\.)[^)]+\)")
    _RAW_URL_RE = re.compile(r"\b(?:https?://|www\.)\S+", re.IGNORECASE)
    _HEADING_RE = re.compile(r"(?m)^\s{0,3}#{1,6}\s+")
    _BULLET_RE = re.compile(r"(?m)^\s*(?:[-*+]\s+|\d+[.)]\s+)")
    _BLOCKQUOTE_RE = re.compile(r"(?m)^\s*>\s?")
    _EMPHASIS_RE = re.compile(r"(?<!\\)(?:\*\*|__|~~|`)")
    _WHITESPACE_RE = re.compile(r"[ \t]+")
    _EXCESS_NEWLINES_RE = re.compile(r"\n{2,}")
    _SPACE_BEFORE_PUNCT_RE = re.compile(r"\s+([,.;:!?])")

    def render(self, text: str) -> str:
        value = str(text or "").strip()
        if not value:
            return ""

        # Do not make Mary read source-code bodies aloud. The full code remains
        # visible in the desktop chat response.
        value = self._FENCED_CODE_RE.sub(" I included the code in the text response. ", value)

        # Speak the useful label, not markdown syntax or a long URL.
        value = self._MARKDOWN_LINK_RE.sub(r"\1", value)
        value = self._RAW_URL_RE.sub("the link", value)

        value = self._HEADING_RE.sub("", value)
        value = self._BULLET_RE.sub("", value)
        value = self._BLOCKQUOTE_RE.sub("", value)
        value = self._EMPHASIS_RE.sub("", value)

        # A few Mary-specific technical forms are clearer when spoken.
        value = re.sub(r"\bMaryV2\b", "Mary V two", value, flags=re.IGNORECASE)
        value = re.sub(r"\bV2\b", "V two", value)

        # Treat line breaks as conversational sentence boundaries instead of
        # asking TTS to infer markdown/list layout.
        lines = [line.strip() for line in value.splitlines() if line.strip()]
        value = " ".join(lines)

        value = self._WHITESPACE_RE.sub(" ", value)
        value = self._SPACE_BEFORE_PUNCT_RE.sub(r"\1", value)
        value = self._EXCESS_NEWLINES_RE.sub("\n", value)
        return value.strip()


def render_spoken_text(text: str) -> str:
    """Convenience function for the default Mary speech renderer."""

    return SpeechRenderer().render(text)
