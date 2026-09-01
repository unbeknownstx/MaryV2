"""Bounded creator-authored interaction preference evidence.

This module intentionally recognizes only a small set of explicit communication
instructions and corrective feedback. It does not infer lifestyle preferences,
facts, emotions, or durable self-state from ordinary conversation.
"""

from __future__ import annotations

from dataclasses import dataclass
import hashlib
import re


@dataclass(frozen=True)
class PreferenceEvidence:
    """One normalized, provenance-safe preference observation."""

    name: str
    signal: str
    category: str
    polarity: float
    strength: float
    confidence: float
    evidence_class: str


_CORRECTIVE_PATTERNS: tuple[tuple[str, float, str], ...] = (
    (
        r"\b(?:(?:that|this)(?: (?:answer|response|reply))?|"
        r"your (?:answer|response|reply)) (?:was|is) "
        r"(?:too|way too) (?:long|wordy|verbose|detailed)\b|"
        r"\b(?:be|make (?:it|your (?:answers?|responses?|replies))) more "
        r"(?:concise|brief)\b|"
        r"\b(?:don'?t|do not) be so (?:wordy|verbose)\b",
        1.0,
        "response_length",
    ),
    (
        r"\b(?:(?:that|this)(?: (?:answer|response|reply))?|"
        r"your (?:answer|response|reply)) (?:was|is) "
        r"(?:too|way too) (?:short|brief|terse)\b|"
        r"\b(?:give|include|add) more (?:detail|context|explanation) "
        r"in (?:your )?(?:answers?|responses?|replies)\b",
        -1.0,
        "response_length",
    ),
    (
        r"\b(?:be|get|make (?:it|your (?:answers?|responses?|replies))) more direct\b|"
        r"\b(?:get|come) (?:straight )?to the point\b|"
        r"\b(?:don'?t|do not) sugarcoat\b",
        1.0,
        "directness",
    ),
    (
        r"\b(?:(?:that|this)(?: (?:answer|response|reply))?|"
        r"your (?:answer|response|reply)) (?:was|is) "
        r"(?:too|way too) (?:blunt|harsh|direct)\b|"
        r"\b(?:be|make (?:it|your (?:answers?|responses?|replies))) "
        r"(?:more )?(?:gentle|tactful)\b",
        -1.0,
        "directness",
    ),
    (
        r"\b(?:don'?t|do not|stop) use(?:ing)? "
        r"(?:bullet(?:ed)?|numbered) (?:points?|lists?)\b|"
        r"\bno (?:more )?(?:bullet(?:ed)?|numbered) (?:points?|lists?)\b",
        -1.0,
        "list_structure",
    ),
    (
        r"\b(?:from now on,? |always |keep )"
        r"(?:use|using) "
        r"(?:bullet(?:ed)?|numbered) (?:points?|lists?)\b",
        1.0,
        "list_structure",
    ),
    (
        r"\b(?:don'?t|do not|stop) (?:ask|asking) "
        r"(?:me )?(?:follow[- ]?up|extra) questions?\b|"
        r"\bno (?:more )?follow[- ]?up questions?\b",
        -1.0,
        "follow_up_questions",
    ),
    (
        r"\b(?:ask|keep asking) (?:me )?(?:a |one )?"
        r"(?:relevant )?follow[- ]?up questions?\b",
        1.0,
        "follow_up_questions",
    ),
)

_EXPLICIT_PATTERNS: tuple[tuple[str, float, str], ...] = (
    (
        r"\bi prefer (?:your )?(?:answers?|responses?|replies) "
        r"(?:to be )?(?:concise|brief|short)\b|"
        r"\bi prefer (?:concise|brief|short) "
        r"(?:answers?|responses?|replies)\b|"
        r"\bi want you to (?:be (?:concise|brief)|keep (?:your )?"
        r"(?:answers?|responses?|replies) (?:concise|brief|short))\b|"
        r"\bplease (?:be (?:concise|brief)|keep (?:your )?"
        r"(?:answers?|responses?|replies) (?:concise|brief|short))\b|"
        r"\bfrom now on,? (?:be (?:concise|brief)|keep (?:your )?"
        r"(?:answers?|responses?|replies) (?:concise|brief|short))\b|"
        r"\bkeep (?:your )?(?:answers?|responses?|replies) "
        r"(?:concise|brief|short)\b",
        1.0,
        "response_length",
    ),
    (
        r"\bi prefer (?:your )?(?:answers?|responses?|replies) "
        r"(?:to be )?(?:detailed|thorough|in[- ]depth)\b|"
        r"\bi prefer (?:detailed|thorough|in[- ]depth) "
        r"(?:answers?|responses?|replies)\b|"
        r"\bi want you to (?:be (?:detailed|thorough)|keep (?:your )?"
        r"(?:answers?|responses?|replies) (?:detailed|thorough|in[- ]depth))\b|"
        r"\bplease (?:be (?:detailed|thorough)|keep (?:your )?"
        r"(?:answers?|responses?|replies) (?:detailed|thorough|in[- ]depth))\b|"
        r"\bfrom now on,? (?:be (?:detailed|thorough)|keep (?:your )?"
        r"(?:answers?|responses?|replies) (?:detailed|thorough|in[- ]depth))\b|"
        r"\bkeep (?:your )?(?:answers?|responses?|replies) "
        r"(?:detailed|thorough|in[- ]depth)\b",
        -1.0,
        "response_length",
    ),
    (
        r"\bi prefer (?:your )?(?:answers?|responses?|replies) "
        r"(?:to be )?direct\b|"
        r"\bi prefer direct (?:answers?|responses?|replies)\b|"
        r"\bi want you to (?:be direct|keep (?:your )?"
        r"(?:answers?|responses?|replies) direct)\b|"
        r"\bplease (?:be direct|keep (?:your )?"
        r"(?:answers?|responses?|replies) direct)\b|"
        r"\bfrom now on,? (?:be direct|keep (?:your )?"
        r"(?:answers?|responses?|replies) direct)\b|"
        r"\bkeep (?:your )?(?:answers?|responses?|replies) direct\b",
        1.0,
        "directness",
    ),
    (
        r"\bi prefer (?:your )?(?:answers?|responses?|replies) "
        r"(?:to be )?(?:gentle|tactful)\b|"
        r"\bi prefer (?:gentle|tactful) "
        r"(?:answers?|responses?|replies)\b|"
        r"\bi want you to (?:be (?:gentle|tactful)|keep (?:your )?"
        r"(?:answers?|responses?|replies) (?:gentle|tactful))\b|"
        r"\bplease (?:be (?:gentle|tactful)|keep (?:your )?"
        r"(?:answers?|responses?|replies) (?:gentle|tactful))\b",
        -1.0,
        "directness",
    ),
)

_CANDIDATE_NAMES = {
    "response_length": "creator interaction response length",
    "directness": "creator interaction directness",
    "list_structure": "creator interaction list structure",
    "follow_up_questions": "creator interaction follow-up questions",
}

_DIRECT_OPENING_RE = re.compile(
    r"^(?:"
    r"i prefer\b|i want you to\b|please\b|from now on\b|"
    r"keep (?:your )?(?:answers?|responses?|replies)\b|"
    r"(?:that|this)(?: (?:answer|response|reply))? (?:was|is)\b|"
    r"your (?:answer|response|reply) (?:was|is)\b|"
    r"be more\b|make (?:it|your (?:answers?|responses?|replies))\b|"
    r"don'?t\b|do not\b|get (?:straight )?to the point\b|"
    r"come (?:straight )?to the point\b|stop\b|no (?:more )?\b|"
    r"always use\b|keep using\b|ask\b|keep asking\b"
    r")",
    re.IGNORECASE,
)


def extract_preference_evidence(text: str) -> PreferenceEvidence | None:
    """Extract one allow-listed explicit interaction signal, if present."""

    normalized = " ".join(str(text or "").casefold().split())
    if not normalized or len(normalized) > 2_000:
        return None
    if any(mark in normalized for mark in ('"', "“", "”", "‘", "’")):
        return None
    if re.search(r"(?:^|\s)'[^']{2,}'(?:[\s.,!?]|$)", normalized):
        return None
    if _DIRECT_OPENING_RE.match(normalized) is None:
        return None
    if re.search(
        r"\b(?:mary|he|she|they|someone|my (?:friend|coworker|boss)) "
        r"(?:said|says|prefers?|told|asked)\b",
        normalized,
    ):
        return None

    for evidence_class, patterns, confidence, strength in (
        ("corrective_feedback", _CORRECTIVE_PATTERNS, 0.92, 0.82),
        ("explicit_preference", _EXPLICIT_PATTERNS, 0.96, 0.88),
    ):
        for pattern, polarity, signal in patterns:
            if re.match(pattern, normalized, flags=re.IGNORECASE):
                return PreferenceEvidence(
                    name=_CANDIDATE_NAMES[signal],
                    signal=signal,
                    category="creator_interaction",
                    polarity=polarity,
                    strength=strength,
                    confidence=confidence,
                    evidence_class=evidence_class,
                )
    return None


def stable_evidence_id(
    *,
    turn_id: str,
    fallback_id: str,
    evidence: PreferenceEvidence,
) -> str:
    """Bind an evidence ID to the canonical turn and normalized signal."""

    event_key = str(turn_id or fallback_id or "").strip()
    digest = hashlib.sha256(
        (
            f"{event_key}|{evidence.signal}|"
            f"{int(evidence.polarity)}|{evidence.evidence_class}"
        ).encode("utf-8")
    ).hexdigest()
    return f"creator_turn_{digest[:32]}"