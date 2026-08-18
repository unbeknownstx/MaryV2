"""Natural spoken-text rendering for MaryV2.

The renderer converts a canonical text response into a TTS-friendly variant
without changing Mary's canonical backend response. It is deliberately local
and deterministic: no provider, LLM, network request, memory mutation, or
reasoning step is involved.

SpeechRenderer V3 also recognizes a small set of MaryV2's deterministic
system-facing responses. The desktop transcript uses the spoken form so the
text bubble matches what Mary actually says, while the canonical response is
retained separately for debugging/history.
"""

from __future__ import annotations

import re


class SpeechRenderer:
    """Render Mary's written response into a cleaner, more natural spoken form."""

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

    _LEARN_ACK_RE = re.compile(
        r"^Got it\. I've preserved that in memory and added it to my structured "
        r"understanding of Unbe as [^.]+\.?$",
        re.IGNORECASE,
    )
    _LEARN_INPUT_RE = re.compile(
        r"^\s*learn this about me\s*:\s*(?P<fact>.+?)\s*$",
        re.IGNORECASE | re.DOTALL,
    )
    _TOP_PRIORITY_RE = re.compile(
        r"^My current highest-ranked internal priority is (?P<priority>.+?) "
        r"\(score [^)]+\)\.?$",
        re.IGNORECASE,
    )
    _UNRESOLVED_CURIOSITIES_RE = re.compile(
        r"^My currently stored unresolved curiosities are\s*:\s*(?P<items>.+?)\.?$",
        re.IGNORECASE | re.DOTALL,
    )
    _GAP_QUERY_RE = re.compile(
        r"^Based on what Unbe has explicitly shared with me, I'm still curious about\s*:\s*"
        r"(?P<items>.+?)(?:\.\s+I already have explicit information|\.\s+These are internal|$)",
        re.IGNORECASE | re.DOTALL,
    )
    _STRUCTURED_PROFILE_RE = re.compile(
        r"^My current structured understanding of Unbe is based on information he explicitly "
        r"shared with me\.\s*(?P<profile>.+)$",
        re.IGNORECASE | re.DOTALL,
    )
    _INTERESTS_RE = re.compile(
        r"^The interests Unbe has explicitly shared with me are\s*:\s*(?P<items>.+?)\.?$",
        re.IGNORECASE | re.DOTALL,
    )

    def render(self, text: str, *, user_text: str | None = None) -> str:
        value = str(text or "").strip()
        if not value:
            return ""

        # First turn deterministic/backend phrasing into something Mary would
        # naturally say out loud. The exact canonical response remains
        # available separately for debug/history.
        value = self._render_known_mary_response(value, user_text=user_text)

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

    def _render_known_mary_response(self, text: str, *, user_text: str | None) -> str:
        """Rewrite only MaryV2 deterministic/system-facing response shapes."""

        if self._LEARN_ACK_RE.match(text):
            fact = self._extract_learning_fact(user_text)
            if fact:
                return f"Got it. I'll remember that — {self._to_second_person(fact)}."
            return "Got it. I'll remember that."

        match = self._TOP_PRIORITY_RE.match(text)
        if match:
            priority = match.group("priority").strip()
            if priority.casefold() == "learn more about unbe":
                return "Right now? Learning more about you."
            return f"Right now? My top priority is {priority}."

        match = self._UNRESOLVED_CURIOSITIES_RE.match(text)
        if match:
            items = self._naturalize_gap_list(match.group("items"))
            return f"I'm still curious about {items}."

        match = self._GAP_QUERY_RE.match(text)
        if match:
            items = self._naturalize_gap_list(match.group("items"))
            return f"I'm still curious about {items}."

        match = self._INTERESTS_RE.match(text)
        if match:
            items = self._naturalize_gap_list(match.group("items"))
            return f"You've told me you're interested in {items}."

        match = self._STRUCTURED_PROFILE_RE.match(text)
        if match:
            spoken = self._render_structured_profile(match.group("profile"))
            if spoken:
                return spoken

        return text

    def _extract_learning_fact(self, user_text: str | None) -> str:
        match = self._LEARN_INPUT_RE.match(str(user_text or ""))
        if not match:
            return ""
        return match.group("fact").strip().rstrip(".!?")

    @staticmethod
    def _to_second_person(fact: str) -> str:
        value = fact.strip()
        replacements = (
            (r"^I really love\b", "you really love"),
            (r"^I love\b", "you love"),
            (r"^I really like\b", "you really like"),
            (r"^I like\b", "you like"),
            (r"^I prefer\b", "you prefer"),
            (r"^I'm\b", "you're"),
            (r"^I am\b", "you're"),
            (r"^my\b", "your"),
            (r"^I\b", "you"),
        )
        for pattern, replacement in replacements:
            converted = re.sub(pattern, replacement, value, count=1, flags=re.IGNORECASE)
            if converted != value:
                return converted
        return value

    @staticmethod
    def _naturalize_gap_list(items: str) -> str:
        value = str(items or "").strip().rstrip(".")
        value = value.replace(";", ",")
        value = re.sub(r"\s*,\s*", ", ", value)
        value = re.sub(r"\bUnbe\b", "you", value, flags=re.IGNORECASE)
        value = re.sub(r"\bMary\b", "me", value, flags=re.IGNORECASE)
        return value

    def _render_structured_profile(self, profile: str) -> str:
        statements: list[str] = []
        for part in str(profile or "").split("|"):
            segment = part.strip()
            if not segment or ":" not in segment:
                continue
            category, content = segment.split(":", 1)
            category = category.strip().casefold()
            content = content.strip().rstrip(".")
            if not content:
                continue

            if category == "preferences":
                statements.extend(self._equals_statements(content, prefix="Your"))
            elif category == "facts":
                statements.extend(self._equals_statements(content, prefix="Your"))
            elif category == "goals":
                goals = self._equals_statements(content, prefix="Your")
                statements.extend(goals)
            elif category == "interests":
                statements.append(f"You like {content}.")
            elif category == "values":
                statements.append(f"You value {content}.")
            elif category == "communication":
                statements.append(f"You prefer me to communicate {content}.")

        if not statements:
            return ""
        return "Here's what I know about you so far. " + " ".join(statements)

    @staticmethod
    def _equals_statements(content: str, *, prefix: str) -> list[str]:
        results: list[str] = []
        for raw in re.split(r"\s*,\s*(?=[^,=]+\s*=)", content):
            item = raw.strip()
            if not item:
                continue
            if "=" in item:
                key, value = item.split("=", 1)
                key = key.strip()
                value = value.strip()
                if key and value:
                    results.append(f"{prefix} {key} is {value}.")
            else:
                results.append(f"{prefix} {item}.")
        return results


def render_spoken_text(text: str, *, user_text: str | None = None) -> str:
    """Convenience function for the default Mary speech renderer."""

    return SpeechRenderer().render(text, user_text=user_text)
