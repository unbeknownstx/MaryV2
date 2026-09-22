"""Deterministic banter opportunity planning for Mary's authored character.

This module does not generate Mary's dialogue and does not own personality,
memory, relationship state, or avatar state. It identifies when a playful shot
is available, proposes a few compact comedic *angles* to Mary's existing
language realization path, and exposes a structural scorer for evaluation.

Any callback cue is session-only context derived from the already-projected
recent conversation. It is never persisted here and never becomes a Mary
memory merely because it was useful for a joke.
"""
from __future__ import annotations

from dataclasses import asdict, dataclass
import re
from typing import Any, Mapping, Sequence


_SERIOUS_PATTERNS = {
    "anger",
    "grief_or_hurt",
    "moral_boundary",
    "pressure",
    "vulnerable_person",
}
_EXPLICIT_INVITE_RE = re.compile(
    r"\b(?:roast me|make fun of me|talk shit|shit talk|trash talk|come at me|"
    r"fight me|clown me|cook me|drag me)\b",
    re.IGNORECASE,
)
_LAUGHTER_RE = re.compile(r"(?:😂|🤣|😭|\blol\b|\blmao\b|\brofl\b|\bhaha+\b|\bhehe+\b)", re.IGNORECASE)
_COMPETITIVE_RE = re.compile(
    r"\b(?:easy|too easy|i(?:'m| am) (?:so )?good|never miss|carried|carry|"
    r"skill issue|won|win|beat you|better than|clutch|pro gamer|owned|cooked)\b",
    re.IGNORECASE,
)
_SELF_OWN_RE = re.compile(
    r"\b(?:oops|my bad|i missed|i died|i lost|i failed|i screwed|i messed|"
    r"that was bad|that was terrible|i threw|i choked|robbed me)\b",
    re.IGNORECASE,
)
_CASUAL_SPARK_RE = re.compile(
    r"\b(?:bro|bruh|dude|nah|fam|this guy|come on|what the hell|what the fuck|"
    r"ain't no way|no way|chat|game|controller|npc|boss|match|round)\b",
    re.IGNORECASE,
)
_GAME_RE = re.compile(
    r"\b(?:game|controller|npc|boss|match|round|level|quest|shot|aim|combo|"
    r"checkpoint|respawn|ranked|lobby|player|enemy)\b",
    re.IGNORECASE,
)
_CHAT_RE = re.compile(r"\b(?:chat|viewer|viewers|stream|comments?)\b", re.IGNORECASE)
_CALLBACK_BLOCKLIST_RE = re.compile(
    r"\b(?:grief|funeral|died in real life|death|trauma|abuse|assault|"
    r"depress(?:ed|ion)?|suicid|self[- ]?harm|medical|diagnos|hospital|"
    r"sick|illness|debt|rent|evict|fired|layoff|breakup|divorce)\b",
    re.IGNORECASE,
)
_GENERIC_INSULT_RE = re.compile(
    r"\b(?:you suck|you(?:'re| are) bad|you(?:'re| are) trash|idiot|moron|"
    r"loser|skill issue|dummy|stupid ass)\b",
    re.IGNORECASE,
)
_ASSISTANTY_RE = re.compile(
    r"\b(?:as an ai|i'm here to help|i am here to help|let me know if|"
    r"would you like me to|hope that helps)\b",
    re.IGNORECASE,
)
_EXPLAINS_JOKE_RE = re.compile(
    r"\b(?:just kidding|that was a joke|i'm joking|i am joking|get it\?)\b",
    re.IGNORECASE,
)
_WORD_RE = re.compile(r"[a-z0-9']+", re.IGNORECASE)


def _clip(value: Any, limit: int = 180) -> str:
    text = " ".join(str(value or "").split())
    if len(text) <= limit:
        return text
    return text[: max(0, limit - 1)].rstrip() + "…"


def _tokens(value: str) -> set[str]:
    return {
        token.casefold()
        for token in _WORD_RE.findall(value or "")
        if len(token) >= 4
    }


@dataclass(frozen=True)
class BanterAngle:
    """A strategy for the existing language model to realize, not joke text."""

    technique: str
    target: str
    cue: str
    instruction: str
    prior: float

    def to_dict(self) -> dict[str, Any]:
        result = asdict(self)
        result["prior"] = round(float(self.prior), 3)
        return result


@dataclass(frozen=True)
class BanterBrief:
    """Bounded turn-level banter opportunity projected into TurnMind."""

    active: bool
    intensity: float
    target: str
    opportunity: str
    callback_cue: str
    callback_scope: str
    candidate_angles: tuple[BanterAngle, ...]
    delivery: tuple[str, ...]
    constraints: tuple[str, ...]
    judge: dict[str, float]
    rationale: str

    def to_dict(self) -> dict[str, Any]:
        return {
            "active": self.active,
            "intensity": round(float(self.intensity), 3),
            "target": self.target,
            "opportunity": self.opportunity,
            "callback_cue": self.callback_cue,
            "callback_scope": self.callback_scope,
            "candidate_angles": [item.to_dict() for item in self.candidate_angles],
            "delivery": list(self.delivery),
            "constraints": list(self.constraints),
            "judge": {key: round(float(value), 3) for key, value in self.judge.items()},
            "rationale": self.rationale,
            "authority": "authored_character_projection_only",
            "persistence": "none",
        }


@dataclass(frozen=True)
class BanterScore:
    """Structural quality score for a realized banter candidate."""

    total: float
    specificity: float
    brevity: float
    callback_strength: float
    character_match: float
    genericness_penalty: float
    repetition_penalty: float
    explanation_penalty: float

    def to_dict(self) -> dict[str, float]:
        return {
            key: round(float(value), 3)
            for key, value in asdict(self).items()
        }


def _callback_cue(recent_conversation: Sequence[Mapping[str, Any]]) -> str:
    """Return one safe, bounded recent user cue for an optional callback."""

    for item in reversed(list(recent_conversation)[-8:]):
        if not isinstance(item, Mapping):
            continue
        if str(item.get("role") or "").strip().lower() != "user":
            continue
        content = _clip(item.get("content"), 150)
        if not content or _CALLBACK_BLOCKLIST_RE.search(content):
            continue
        words = _WORD_RE.findall(content)
        if 4 <= len(words) <= 24:
            return content
    return ""


def _target_for(text: str, *, explicit_invite: bool, self_own: bool) -> str:
    if _CHAT_RE.search(text):
        return "chat"
    if _GAME_RE.search(text):
        return "game_or_situation"
    if explicit_invite or self_own:
        return "creator"
    return "situation"


def build_banter_brief(
    input_text: str,
    *,
    recent_conversation: Sequence[Mapping[str, Any]] = (),
    familiarity: str = "developing",
    drive: str = "react",
    playfulness: float = 0.5,
    allow_teasing: bool = True,
    active_patterns: Sequence[str] = (),
) -> BanterBrief:
    """Identify a banter opportunity without generating or persisting dialogue."""

    text = _clip(input_text, 500)
    patterns = {str(item).strip().lower() for item in active_patterns if str(item).strip()}
    serious = bool(patterns.intersection(_SERIOUS_PATTERNS))
    explicit_invite = bool(_EXPLICIT_INVITE_RE.search(text))
    laughter = bool(_LAUGHTER_RE.search(text))
    competitive = bool(_COMPETITIVE_RE.search(text))
    self_own = bool(_SELF_OWN_RE.search(text))
    casual_spark = bool(_CASUAL_SPARK_RE.search(text))
    close = str(familiarity or "").strip().lower() == "familiar"
    playful = max(0.0, min(1.0, float(playfulness or 0.0)))

    if not allow_teasing:
        rationale = "turn disposition disallows teasing"
        active = False
    elif serious:
        rationale = "serious character context suppresses optional banter"
        active = False
    else:
        active = bool(
            str(drive or "").strip().lower() == "tease"
            or explicit_invite
            or competitive
            or self_own
            or laughter
            or (close and playful >= 0.78 and casual_spark)
        )
        rationale = (
            "specific playful opportunity found"
            if active
            else "no specific comedic angle; natural conversation wins over forced sass"
        )

    intensity = 0.0
    if active:
        intensity = 0.34
        intensity += 0.26 if explicit_invite else 0.0
        intensity += 0.18 if str(drive or "").strip().lower() == "tease" else 0.0
        intensity += 0.10 if competitive or self_own else 0.0
        intensity += 0.08 if laughter else 0.0
        intensity += 0.08 if close else 0.0
        intensity += 0.06 * playful
        intensity = max(0.35, min(0.92, intensity))

    target = _target_for(text, explicit_invite=explicit_invite, self_own=self_own)
    callback = _callback_cue(recent_conversation) if active and close else ""
    angles: list[BanterAngle] = []

    if active and callback:
        angles.append(BanterAngle(
            technique="callback",
            target=target,
            cue=callback,
            instruction=(
                "Optionally twist this recent session cue into the current beat. "
                "Do not quote it mechanically and do not present it as durable memory."
            ),
            prior=0.90,
        ))
    if active and (competitive or self_own or explicit_invite):
        angles.append(BanterAngle(
            technique="dry_reversal",
            target=target,
            cue=_clip(text, 120),
            instruction=(
                "Invert the current framing in one short deadpan observation; "
                "the specificity should carry the joke."
            ),
            prior=0.86,
        ))
    if active and close and target == "creator":
        angles.append(BanterAngle(
            technique="affectionate_roast",
            target=target,
            cue=_clip(text, 120),
            instruction=(
                "Tease the specific behavior or moment, not identity, appearance, "
                "ability as a person, or a genuine vulnerability."
            ),
            prior=0.82,
        ))
    if active and (laughter or casual_spark or target in {"chat", "game_or_situation"}):
        angles.append(BanterAngle(
            technique="absurd_escalation",
            target=target,
            cue=_clip(text, 120),
            instruction=(
                "Escalate the situation into one ridiculous implication, then stop "
                "before explaining the bit."
            ),
            prior=0.72,
        ))
    if active:
        angles.append(BanterAngle(
            technique="specific_observation",
            target=target,
            cue=_clip(text, 120),
            instruction=(
                "Notice one concrete contradiction, overconfidence, tiny failure, "
                "or situational detail and land one compact line on it."
            ),
            prior=0.78,
        ))

    unique: list[BanterAngle] = []
    seen: set[str] = set()
    for angle in angles:
        if angle.technique in seen:
            continue
        seen.add(angle.technique)
        unique.append(angle)
        if len(unique) >= 3:
            break

    return BanterBrief(
        active=active,
        intensity=intensity,
        target=target if active else "none",
        opportunity=(
            "explicit_invite" if explicit_invite
            else "self_own" if self_own
            else "competitive" if competitive
            else "shared_amusement" if laughter
            else "casual_spark" if active
            else "none"
        ),
        callback_cue=callback,
        callback_scope="session_only" if callback else "none",
        candidate_angles=tuple(unique),
        delivery=(
            "one main punchline",
            "deadpan or quick timing",
            "let the landing breathe",
            "warmth underneath the edge",
        ) if active else (),
        constraints=(
            "A joke is optional; do not force one when the angle is weak.",
            "Specific observation beats a generic insult.",
            "Do not explain the joke after it lands.",
            "Do not pile on with multiple insults.",
            "Never target genuine pain, protected traits, appearance, trauma, or an inferred private insecurity.",
            "Do not invent a motive, feeling, failure, or history just to make the joke work.",
            "Serious context overrides banter immediately.",
        ),
        judge={
            "specificity": 1.00,
            "surprise": 0.90,
            "brevity": 0.85,
            "callback_strength": 0.75 if callback else 0.20,
            "character_match": 1.00,
            "genericness_penalty": 1.00,
            "repetition_penalty": 0.90,
            "unnecessary_cruelty_penalty": 1.00,
        },
        rationale=rationale,
    )


def score_banter_candidate(
    candidate: str,
    *,
    brief: BanterBrief | Mapping[str, Any],
    current_input: str = "",
    recent_mary_lines: Sequence[str] = (),
) -> BanterScore:
    """Score a realized line structurally without another model call."""

    value = _clip(candidate, 500)
    words = _WORD_RE.findall(value)
    word_count = len(words)

    if isinstance(brief, BanterBrief):
        callback = brief.callback_cue
        active = brief.active
    else:
        callback = str(brief.get("callback_cue") or "")
        active = bool(brief.get("active"))

    anchors = _tokens(current_input) | _tokens(callback)
    candidate_tokens = _tokens(value)
    overlap = len(anchors.intersection(candidate_tokens))
    specificity = min(1.0, 0.28 + (0.18 * overlap)) if anchors else 0.45
    if re.search(r"\b(?:that|this|it)\b", value, flags=re.IGNORECASE) and current_input:
        specificity = min(1.0, specificity + 0.08)

    if 4 <= word_count <= 18:
        brevity = 1.0
    elif 2 <= word_count <= 26:
        brevity = 0.80
    elif word_count <= 36:
        brevity = 0.52
    else:
        brevity = 0.22

    callback_strength = 0.0
    if callback:
        callback_tokens = _tokens(callback)
        if callback_tokens:
            callback_strength = min(
                1.0,
                len(callback_tokens.intersection(candidate_tokens))
                / max(1, min(5, len(callback_tokens))),
            )

    genericness_penalty = 1.0 if _GENERIC_INSULT_RE.search(value) else 0.0
    assistant_penalty = 0.8 if _ASSISTANTY_RE.search(value) else 0.0
    explanation_penalty = 1.0 if _EXPLAINS_JOKE_RE.search(value) else 0.0

    normalized = " ".join(value.casefold().split())
    repetition_penalty = 0.0
    for prior in list(recent_mary_lines)[-5:]:
        prior_norm = " ".join(str(prior or "").casefold().split())
        if not prior_norm:
            continue
        if normalized == prior_norm:
            repetition_penalty = 1.0
            break
        shared = _tokens(normalized).intersection(_tokens(prior_norm))
        if len(shared) >= 5:
            repetition_penalty = max(repetition_penalty, 0.55)

    character_match = 1.0
    character_match -= 0.45 * genericness_penalty
    character_match -= 0.45 * assistant_penalty
    character_match -= 0.30 * explanation_penalty
    if not active:
        character_match = min(character_match, 0.45)
    character_match = max(0.0, min(1.0, character_match))

    total = (
        0.28 * specificity
        + 0.20 * brevity
        + 0.12 * callback_strength
        + 0.40 * character_match
        - 0.20 * genericness_penalty
        - 0.14 * repetition_penalty
        - 0.12 * explanation_penalty
    )
    total = max(0.0, min(1.0, total))

    return BanterScore(
        total=total,
        specificity=specificity,
        brevity=brevity,
        callback_strength=callback_strength,
        character_match=character_match,
        genericness_penalty=genericness_penalty,
        repetition_penalty=repetition_penalty,
        explanation_penalty=explanation_penalty,
    )
