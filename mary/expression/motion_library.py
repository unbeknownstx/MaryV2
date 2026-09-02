"""Semantic motion selection for Mary's presentation layer.

AIRI and modern virtual-character runtimes increasingly treat animation as a
retrieval problem rather than a pile of ``if emotion == ...`` branches.  Mary
keeps that idea deliberately subordinate to her existing PerformancePacket:
character/cognition decide delivery first; this catalog only chooses a motion
that can visually realize those already-authoritative cues.

The catalog contains metadata, never executable animation code.  Binary motion
assets (VRMA/FBX/BVH/etc.) remain external/local and may be replaced freely.
"""
from __future__ import annotations

from dataclasses import asdict, dataclass, field
import json
from pathlib import Path
from typing import Any, Iterable, Mapping, Sequence


def _tokens(*values: Any) -> set[str]:
    output: set[str] = set()
    for value in values:
        text = str(value or "").replace("-", "_").replace("/", "_").casefold()
        for token in text.replace(",", " ").replace(";", " ").split():
            token = token.strip("_ .:!?()[]{}\"'")
            if token:
                output.add(token)
    return output


@dataclass(frozen=True)
class MotionAsset:
    motion_id: str
    tags: tuple[str, ...]
    energy_min: float = 0.0
    energy_max: float = 1.0
    contexts: tuple[str, ...] = ("private", "stream", "performance")
    interruptible: bool = True
    loop: bool = False
    asset_uri: str = ""
    source: str = "mary_builtin"
    license: str = "metadata_only"
    notes: str = ""

    def to_dict(self) -> dict[str, Any]:
        payload = asdict(self)
        payload["energy_min"] = round(max(0.0, min(1.0, float(self.energy_min))), 3)
        payload["energy_max"] = round(max(0.0, min(1.0, float(self.energy_max))), 3)
        return payload


@dataclass(frozen=True)
class MotionCue:
    segment_index: int
    motion_id: str
    score: float
    reason: str
    interruptible: bool
    loop: bool
    asset_uri: str = ""

    def to_dict(self) -> dict[str, Any]:
        payload = asdict(self)
        payload["score"] = round(max(0.0, min(1.0, float(self.score))), 3)
        return payload


class MotionLibrary:
    """Small deterministic semantic retriever with an embedding-ready contract."""

    VERSION = "1"

    def __init__(self, motions: Iterable[MotionAsset] = ()) -> None:
        self._motions: dict[str, MotionAsset] = {item.motion_id: item for item in motions if item.motion_id}
        if not self._motions:
            self._motions = {item.motion_id: item for item in _builtin_motions()}

    @classmethod
    def from_json(cls, path: str | Path) -> "MotionLibrary":
        source = Path(path)
        if not source.exists():
            return cls()
        try:
            payload = json.loads(source.read_text(encoding="utf-8"))
        except Exception:
            return cls()
        motions: list[MotionAsset] = []
        for raw in list(payload.get("motions") or [])[:1000]:
            if not isinstance(raw, dict):
                continue
            try:
                motions.append(MotionAsset(
                    motion_id=str(raw.get("id") or raw.get("motion_id") or "")[:120],
                    tags=tuple(str(item)[:80] for item in list(raw.get("tags") or [])[:40]),
                    energy_min=float(raw.get("energy_min", 0.0)),
                    energy_max=float(raw.get("energy_max", 1.0)),
                    contexts=tuple(str(item)[:40] for item in list(raw.get("contexts") or ["private", "stream", "performance"])[:12]),
                    interruptible=bool(raw.get("interruptible", True)),
                    loop=bool(raw.get("loop", False)),
                    asset_uri=str(raw.get("asset_uri") or "")[:500],
                    source=str(raw.get("source") or "external")[:160],
                    license=str(raw.get("license") or "unknown")[:120],
                    notes=str(raw.get("notes") or "")[:500],
                ))
            except Exception:
                continue
        return cls(motions)

    def add(self, motion: MotionAsset) -> None:
        if not motion.motion_id:
            raise ValueError("motion_id is required")
        self._motions[motion.motion_id] = motion

    def select(self, segment: Mapping[str, Any] | Any, *, social_context: str = "private") -> MotionCue:
        def value(name: str, default: Any = "") -> Any:
            if isinstance(segment, Mapping):
                return segment.get(name, default)
            return getattr(segment, name, default)

        index = int(value("index", 0) or 0)
        energy = max(0.0, min(1.0, float(value("energy", .45) or .45)))
        query_tokens = _tokens(
            value("role", ""), value("profile", ""), value("expression", ""),
            value("gesture_style", ""), value("gaze_style", ""), value("head_style", ""),
        )
        context = str(social_context or "private").strip().casefold()
        best: tuple[float, MotionAsset, str] | None = None
        for motion in self._motions.values():
            if motion.contexts and context not in {item.casefold() for item in motion.contexts}:
                continue
            tags = _tokens(*motion.tags, motion.motion_id)
            overlap = len(query_tokens & tags)
            union = max(1, len(query_tokens | tags))
            lexical = overlap / union
            center = (max(0.0, motion.energy_min) + min(1.0, motion.energy_max)) / 2.0
            energy_fit = 1.0 - min(1.0, abs(energy - center))
            in_band = motion.energy_min <= energy <= motion.energy_max
            score = lexical * .72 + energy_fit * .20 + (.08 if in_band else 0.0)
            if motion.motion_id == "talk_neutral" and overlap == 0:
                score = max(score, .20)
            reason = f"semantic_overlap={overlap};energy_fit={energy_fit:.2f}"
            if best is None or score > best[0]:
                best = (score, motion, reason)
        if best is None:
            fallback = _builtin_motions()[0]
            best = (.1, fallback, "fallback")
        score, motion, reason = best
        return MotionCue(
            segment_index=index,
            motion_id=motion.motion_id,
            score=max(0.0, min(1.0, score)),
            reason=reason,
            interruptible=bool(motion.interruptible),
            loop=bool(motion.loop),
            asset_uri=motion.asset_uri,
        )

    def plan(self, segments: Sequence[Mapping[str, Any] | Any], *, social_context: str = "private") -> tuple[MotionCue, ...]:
        return tuple(self.select(item, social_context=social_context) for item in list(segments)[:16])

    def snapshot(self) -> dict[str, Any]:
        return {
            "version": self.VERSION,
            "count": len(self._motions),
            "motions": [item.to_dict() for item in self._motions.values()],
            "policy": "presentation retrieval only; motion metadata/assets never define Mary identity or cognition",
        }


def _builtin_motions() -> tuple[MotionAsset, ...]:
    # These are semantic slots, not bundled copyrighted animation files.  The
    # same IDs can later resolve to licensed VRMA/FBX/BVH assets per node.
    return (
        MotionAsset("talk_neutral", ("natural", "neutral", "conversational", "develop"), .15, .65, loop=True),
        MotionAsset("listen_attentive", ("listening", "attentive", "engaged", "soft", "natural"), .05, .5, loop=True),
        MotionAsset("explain_small", ("explain", "controlled", "thoughtful", "develop", "natural"), .2, .6),
        MotionAsset("explain_animated", ("explain", "animated", "excited", "emphatic", "develop"), .55, 1.0),
        MotionAsset("shrug_dry", ("dry", "sarcastic", "amused", "shrug", "teasing"), .2, .7),
        MotionAsset("teasing_point", ("playful", "teasing", "amused", "point", "quick"), .45, .9),
        MotionAsset("warm_acknowledge", ("warm", "soft", "gentle", "supportive", "opening", "landing"), .05, .5),
        MotionAsset("serious_hold", ("serious", "controlled", "firm", "focused", "landing"), .15, .55),
        MotionAsset("thinking_pause", ("thoughtful", "thinking", "pause", "reflective"), .05, .45),
        MotionAsset("boundary_small", ("boundary", "firm", "controlled", "edge"), .25, .65),
        MotionAsset("surprised_react", ("surprised", "react", "quick", "opening"), .45, .95),
        MotionAsset("laugh_small", ("laugh", "amused", "playful", "warm"), .35, .75),
    )


DEFAULT_MOTION_LIBRARY = MotionLibrary()
