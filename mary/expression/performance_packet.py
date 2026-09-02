"""Surface-neutral realtime performance contract for MaryV2.

A Mary turn is more than text.  This module converts the already-authoritative
``DeliveryPlan`` into one bounded packet that any presentation surface can
render.  It is intentionally *presentation only*: it cannot create memories,
beliefs, creator facts, relationship evidence, or durable character state.

The packet also contains a deterministic speech segmentation plan.  Current
surfaces may still synthesize the whole response in one TTS request; the
segments make the protocol ready for low-latency progressive TTS without
making extra paid API calls by default.
"""
from __future__ import annotations

from dataclasses import asdict, dataclass, field
import re
from typing import Any, Mapping

from .delivery_plan import DeliveryPlan
from .motion_library import DEFAULT_MOTION_LIBRARY, MotionCue


_PACKET_VERSION = "1"
_MAX_SEGMENTS = 5


@dataclass(frozen=True)
class PerformanceSegment:
    index: int
    text: str
    start: float
    end: float
    pause_after_ms: int
    role: str
    profile: str
    energy: float
    warmth: float
    pace: float
    expression: str
    gesture_style: str
    gaze_style: str
    head_style: str
    interruptible: bool = True

    def to_dict(self) -> dict[str, Any]:
        payload = asdict(self)
        for key in ("start", "end", "energy", "warmth", "pace"):
            payload[key] = round(float(payload[key]), 3)
        return payload


@dataclass(frozen=True)
class MicroReaction:
    style: str = "none"
    expression: str = "neutral"
    gaze_style: str = "engaged"
    head_style: str = "natural"
    duration_ms: int = 0
    intensity: float = 0.0

    def to_dict(self) -> dict[str, Any]:
        payload = asdict(self)
        payload["intensity"] = round(float(self.intensity), 3)
        return payload


@dataclass(frozen=True)
class PerformancePacket:
    """One surface-neutral performance score for a completed Mary turn."""

    text: str
    delivery: dict[str, Any]
    segments: tuple[PerformanceSegment, ...] = ()
    pre_reaction: MicroReaction = field(default_factory=MicroReaction)
    motion_cues: tuple[MotionCue, ...] = ()
    social_context: str = "private"
    initiative: bool = False
    source_authority: str = "creator_turn"
    interruptible: bool = True
    version: str = _PACKET_VERSION
    policy: str = (
        "presentation-only projection; surfaces may ignore unsupported cues; "
        "never identity/memory/relationship authority"
    )

    def to_dict(self) -> dict[str, Any]:
        return {
            "version": self.version,
            "text": self.text,
            "delivery": dict(self.delivery),
            "segments": [segment.to_dict() for segment in self.segments],
            "pre_reaction": self.pre_reaction.to_dict(),
            "motion_cues": [cue.to_dict() for cue in self.motion_cues],
            "social_context": self.social_context,
            "initiative": bool(self.initiative),
            "source_authority": self.source_authority,
            "interruptible": bool(self.interruptible),
            "policy": self.policy,
        }


def build_performance_packet(
    text: str,
    delivery_plan: DeliveryPlan | Mapping[str, Any] | None,
    *,
    social_context: str = "private",
    initiative: bool = False,
    source_authority: str = "creator_turn",
) -> PerformancePacket:
    """Build the canonical surface packet without calling a model or TTS."""

    value = " ".join(str(text or "").split()).strip()
    delivery = _delivery_dict(delivery_plan)
    context = _social_context(social_context)
    segments = tuple(_segments(value, delivery))
    reaction = _micro_reaction(delivery)
    motion_cues = DEFAULT_MOTION_LIBRARY.plan(segments, social_context=context)
    interruptible = bool(delivery.get("interruptible", True))
    return PerformancePacket(
        text=value,
        delivery=delivery,
        segments=segments,
        pre_reaction=reaction,
        motion_cues=motion_cues,
        social_context=context,
        initiative=bool(initiative),
        source_authority=_clip(source_authority or "creator_turn", 80),
        interruptible=interruptible,
    )


def _delivery_dict(plan: DeliveryPlan | Mapping[str, Any] | None) -> dict[str, Any]:
    if isinstance(plan, DeliveryPlan):
        return plan.to_dict()
    if isinstance(plan, Mapping):
        # Make a bounded JSON-friendly view rather than trusting arbitrary
        # metadata from a surface/plugin to become presentation authority.
        allowed = {
            "profile", "energy", "warmth", "pace", "stability", "style",
            "emphasis", "pause_style", "avatar_expression", "gesture_energy",
            "gesture_style", "gaze_style", "head_style", "reaction_style",
            "performance_beats", "interruptible", "rationale", "metadata",
        }
        return {str(k): v for k, v in dict(plan).items() if str(k) in allowed}
    return DeliveryPlan().to_dict()


def _segments(text: str, delivery: Mapping[str, Any]) -> list[PerformanceSegment]:
    if not text:
        return []

    chunks = _speech_chunks(text)
    lengths = [max(1, len(item)) for item in chunks]
    total = float(sum(lengths)) or 1.0
    cursor = 0.0
    beats = [item for item in list(delivery.get("performance_beats", []) or []) if isinstance(item, Mapping)]
    result: list[PerformanceSegment] = []

    for index, (chunk, length) in enumerate(zip(chunks, lengths)):
        start = cursor / total
        cursor += length
        end = cursor / total
        beat = _beat_for_fraction(beats, (start + end) / 2.0)
        role = "opening" if index == 0 else ("landing" if index == len(chunks) - 1 else "develop")
        result.append(
            PerformanceSegment(
                index=index,
                text=chunk,
                start=start,
                end=end,
                pause_after_ms=_pause_after(chunk, delivery, is_last=index == len(chunks) - 1),
                role=str(beat.get("role") or role),
                profile=_clip(delivery.get("profile") or "conversational", 48),
                energy=_number(beat.get("energy", delivery.get("energy", 0.45)), 0.0, 1.0),
                warmth=_number(beat.get("warmth", delivery.get("warmth", 0.55)), 0.0, 1.0),
                pace=_number(delivery.get("pace", 1.0), 0.85, 1.15),
                expression=_clip(beat.get("expression") or delivery.get("avatar_expression") or "neutral", 48),
                gesture_style=_clip(beat.get("gesture_style") or delivery.get("gesture_style") or "natural", 48),
                gaze_style=_clip(beat.get("gaze_style") or delivery.get("gaze_style") or "engaged", 48),
                head_style=_clip(beat.get("head_style") or delivery.get("head_style") or "natural", 48),
                interruptible=bool(delivery.get("interruptible", True)),
            )
        )
    return result


def _speech_chunks(text: str) -> list[str]:
    """Return 1..5 natural chunks while keeping Mary wording unchanged."""

    sentences = [item.strip() for item in re.split(r"(?<=[.!?])\s+", text) if item.strip()]
    if not sentences:
        return [text[:4000]]

    chunks: list[str] = []
    for sentence in sentences:
        # A very long sentence can start sounding earlier at a strong clause
        # boundary.  Avoid tiny fragments: those create robotic TTS cadence.
        if len(sentence) > 220:
            pieces = [item.strip() for item in re.split(r"(?<=[,;:—–])\s+", sentence) if item.strip()]
            current = ""
            for piece in pieces:
                candidate = f"{current} {piece}".strip()
                if current and len(candidate) > 190:
                    chunks.append(current)
                    current = piece
                else:
                    current = candidate
            if current:
                chunks.append(current)
        else:
            chunks.append(sentence)

    # Bound streaming complexity.  Preserve an opener and landing, merge the
    # middle rather than dropping any of Mary's words.
    if len(chunks) > _MAX_SEGMENTS:
        head = chunks[:2]
        tail = chunks[-2:]
        middle = " ".join(chunks[2:-2]).strip()
        chunks = head + ([middle] if middle else []) + tail
    return chunks[:_MAX_SEGMENTS]


def _beat_for_fraction(beats: list[Mapping[str, Any]], fraction: float) -> Mapping[str, Any]:
    for beat in beats:
        try:
            start = float(beat.get("start", 0.0))
            end = float(beat.get("end", 1.0))
        except (TypeError, ValueError):
            continue
        if start <= fraction <= end:
            return beat
    return beats[-1] if beats else {}


def _pause_after(text: str, delivery: Mapping[str, Any], *, is_last: bool) -> int:
    if is_last:
        return 0
    pause_style = str(delivery.get("pause_style") or "conversational").lower()
    base = {
        "compressed": 90,
        "quick": 100,
        "natural": 145,
        "conversational": 145,
        "controlled": 175,
        "thoughtful": 240,
        "soft": 230,
    }.get(pause_style, 145)
    if text.rstrip().endswith("?"):
        base += 55
    elif text.rstrip().endswith("!"):
        base = max(80, base - 30)
    return int(max(70, min(420, base)))


def _micro_reaction(delivery: Mapping[str, Any]) -> MicroReaction:
    style = str(delivery.get("reaction_style") or "none").strip().lower()
    expression = str(delivery.get("avatar_expression") or "neutral").strip().lower()
    energy = _number(delivery.get("energy", 0.4), 0.0, 1.0)
    if style in {"", "none", "neutral"} and expression == "neutral":
        return MicroReaction()

    # The reaction is intentionally brief: it gives the face/body a head start
    # while TTS prepares without pretending that reasoning happened faster.
    duration = 160 + int(180 * energy)
    if style in {"boundary", "edge", "focus"}:
        duration = 170
    elif style in {"fluster", "laugh", "soft_smile"}:
        duration = 260
    return MicroReaction(
        style=_clip(style or expression, 48),
        expression=_clip(expression, 48),
        gaze_style=_clip(delivery.get("gaze_style") or "engaged", 48),
        head_style=_clip(delivery.get("head_style") or "natural", 48),
        duration_ms=max(120, min(420, duration)),
        intensity=energy,
    )


def _social_context(value: str) -> str:
    mode = str(value or "private").strip().lower()
    return mode if mode in {"private", "casual", "focus", "stream", "performance"} else "private"


def _clip(value: Any, limit: int) -> str:
    text = str(value or "").strip()
    return text[: max(1, int(limit))]


def _number(value: Any, minimum: float, maximum: float) -> float:
    try:
        number = float(value)
    except (TypeError, ValueError):
        number = minimum
    return max(minimum, min(maximum, number))
