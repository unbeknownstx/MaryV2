"""Provider-neutral cross-media creative production planning for MaryV2.

The production layer turns creator intent + project context into bounded
capability jobs.  It does not execute, spend money, publish, or silently replace
human-authored reference art.  A drawing, manuscript page, voice-actor take, or
storyboard can be carried as provenance-bearing source material and remain the
creative authority for a generated derivative.
"""
from __future__ import annotations
from dataclasses import asdict, dataclass, field
from enum import Enum
from hashlib import sha256
from typing import Any, Iterable
from uuid import uuid4


class ProductionStage(str, Enum):
    IDEA = "idea"
    SCRIPT = "script"
    STORYBOARD = "storyboard"
    ASSETS = "assets"
    RENDER = "render"
    EDIT = "edit"
    REVIEW = "review"
    PUBLISH = "publish"


class ProductionFormat(str, Enum):
    SHORT_VIDEO = "short_video"
    ANIMATION = "animation"
    MANGA = "manga"
    BOOK = "book"
    AUDIO_DRAMA = "audio_drama"
    MIXED_MEDIA = "mixed_media"


@dataclass(frozen=True)
class CreativeReference:
    """Creator-owned or approved source material used by a production."""

    uri: str
    kind: str
    role: str = "reference"
    provenance: str = "creator_authored"
    notes: str = ""

    def to_dict(self) -> dict[str, Any]:
        return asdict(self)


@dataclass(frozen=True)
class CharacterAnchor:
    character_id: str
    display_name: str
    visual_traits: tuple[str, ...] = ()
    wardrobe: tuple[str, ...] = ()
    voice_profile: str = ""
    behavior_notes: tuple[str, ...] = ()
    reference_assets: tuple[str, ...] = ()
    provenance: str = "creator_authored"

    def to_dict(self) -> dict[str, Any]:
        return asdict(self)


@dataclass(frozen=True)
class Shot:
    """A bounded production unit.

    The historical name ``Shot`` remains for compatibility.  For books/manga it
    may represent a scene/page/panel sequence rather than a literal camera shot.
    """

    shot_id: str
    duration_s: float
    framing: str
    action: str
    dialogue: str = ""
    environment: str = ""
    camera: str = ""
    expression: str = "neutral"
    gesture: str = "natural"
    audio_notes: str = ""
    continuity: tuple[str, ...] = ()
    source_refs: tuple[str, ...] = ()

    def to_dict(self) -> dict[str, Any]:
        return asdict(self)


@dataclass(frozen=True)
class ProductionPlan:
    production_id: str
    title: str
    objective: str
    format: str
    aspect_ratio: str
    target_seconds: int
    stage: str
    characters: tuple[CharacterAnchor, ...]
    shots: tuple[Shot, ...]
    deliverables: tuple[str, ...]
    provider_preferences: dict[str, str] = field(default_factory=dict)
    approval_gates: tuple[str, ...] = (
        "paid_capability",
        "external_render",
        "filesystem_write",
        "publish",
    )
    provenance: str = "creator_directed"
    version: str = "2"
    references: tuple[CreativeReference, ...] = ()
    creative_intent: tuple[str, ...] = ()
    style_constraints: tuple[str, ...] = ()
    budget_ceiling_usd: float | None = None

    def to_dict(self) -> dict[str, Any]:
        data = asdict(self)
        data["characters"] = [item.to_dict() for item in self.characters]
        data["shots"] = [item.to_dict() for item in self.shots]
        data["references"] = [item.to_dict() for item in self.references]
        return data

    @property
    def fingerprint(self) -> str:
        core = (
            f"{self.title}|{self.objective}|{self.format}|{self.target_seconds}|"
            + "|".join(shot.action for shot in self.shots)
            + "|".join(ref.uri for ref in self.references)
        )
        return sha256(core.encode("utf-8")).hexdigest()[:16]


def build_production_plan(
    *,
    title: str,
    objective: str,
    shots: Iterable[Shot],
    characters: Iterable[CharacterAnchor] = (),
    format: str = ProductionFormat.SHORT_VIDEO.value,
    aspect_ratio: str = "9:16",
    target_seconds: int = 30,
    deliverables: Iterable[str] = ("master_video", "thumbnail", "caption"),
    provider_preferences: dict[str, str] | None = None,
    references: Iterable[CreativeReference] = (),
    creative_intent: Iterable[str] = (),
    style_constraints: Iterable[str] = (),
    budget_ceiling_usd: float | None = None,
) -> ProductionPlan:
    title = " ".join(str(title).split())[:160]
    objective = " ".join(str(objective).split())[:4000]
    if not title or not objective:
        raise ValueError("title and objective are required")
    shot_tuple = tuple(shots)
    if not shot_tuple or len(shot_tuple) > 128:
        raise ValueError("production requires 1..128 production units")
    seconds = max(1, min(int(target_seconds), 14400))
    normalized_format = str(format or ProductionFormat.SHORT_VIDEO.value).strip().lower()[:64]
    budget = None if budget_ceiling_usd is None else max(0.0, min(float(budget_ceiling_usd), 1_000_000.0))
    return ProductionPlan(
        production_id=str(uuid4()),
        title=title,
        objective=objective,
        format=normalized_format,
        aspect_ratio=str(aspect_ratio)[:16],
        target_seconds=seconds,
        stage=ProductionStage.STORYBOARD.value,
        characters=tuple(characters)[:32],
        shots=shot_tuple,
        deliverables=tuple(str(x)[:80] for x in deliverables)[:32],
        provider_preferences={str(k)[:80]: str(v)[:160] for k, v in dict(provider_preferences or {}).items()},
        references=tuple(references)[:128],
        creative_intent=tuple(str(x)[:500] for x in creative_intent)[:32],
        style_constraints=tuple(str(x)[:500] for x in style_constraints)[:32],
        budget_ceiling_usd=budget,
    )


def _job(
    kind: str,
    plan: ProductionPlan,
    *,
    shot: Shot | None = None,
    payload: dict[str, Any] | None = None,
    approval: bool = True,
    reason: str = "external_or_consequential_capability",
) -> dict[str, Any]:
    row: dict[str, Any] = {
        "kind": kind,
        "production_id": plan.production_id,
        "requires_approval": bool(approval),
        "approval_reason": reason if approval else "none",
        "budget_ceiling_usd": plan.budget_ceiling_usd,
        "provider_preference": plan.provider_preferences.get(kind, ""),
    }
    if shot is not None:
        row["shot_id"] = shot.shot_id
    row.update(dict(payload or {}))
    return row


def _visual_prompt(plan: ProductionPlan, shot: Shot) -> dict[str, Any]:
    return {
        "action": shot.action,
        "environment": shot.environment,
        "camera": shot.camera,
        "framing": shot.framing,
        "expression": shot.expression,
        "gesture": shot.gesture,
        "continuity": list(shot.continuity),
        "source_refs": list(shot.source_refs),
        "creative_intent": list(plan.creative_intent),
        "style_constraints": list(plan.style_constraints),
        "reference_assets": [ref.to_dict() for ref in plan.references[:24]],
        "policy": "preserve creator-authored references and character continuity; generation is a derivative tool, not authorship authority",
    }


def capability_jobs(plan: ProductionPlan) -> list[dict[str, Any]]:
    """Translate one plan into bounded provider-neutral jobs.

    This never executes or authorizes a job. Unknown/unconfigured capabilities
    are expected to appear unavailable in route previews until a node/service
    explicitly advertises them.
    """

    fmt = str(plan.format or "short_video").strip().lower()
    jobs: list[dict[str, Any]] = []

    if fmt == ProductionFormat.BOOK.value:
        for shot in plan.shots:
            jobs.append(_job(
                "text.develop",
                plan,
                shot=shot,
                payload={
                    "brief": shot.action,
                    "dialogue": shot.dialogue,
                    "continuity": list(shot.continuity),
                    "source_refs": list(shot.source_refs),
                },
                approval=False,
            ))
        jobs.append(_job("text.edit", plan, payload={"unit_ids": [x.shot_id for x in plan.shots]}, approval=False))
        jobs.append(_job("document.assemble", plan, payload={"deliverables": list(plan.deliverables)}))
        return jobs

    if fmt == ProductionFormat.MANGA.value:
        for shot in plan.shots:
            jobs.append(_job("image.generate", plan, shot=shot, payload={"prompt": _visual_prompt(plan, shot)}))
            if shot.dialogue:
                jobs.append(_job("layout.letter", plan, shot=shot, payload={"dialogue": shot.dialogue}, approval=False))
        jobs.append(_job("document.assemble", plan, payload={"deliverables": list(plan.deliverables)}))
        return jobs

    if fmt == ProductionFormat.AUDIO_DRAMA.value:
        for shot in plan.shots:
            if shot.dialogue:
                jobs.append(_job("voice.synthesize", plan, shot=shot, payload={"text": shot.dialogue}))
            if shot.audio_notes:
                jobs.append(_job("audio.sfx.generate", plan, shot=shot, payload={"brief": shot.audio_notes}))
        jobs.append(_job("audio.edit", plan, payload={"unit_ids": [x.shot_id for x in plan.shots]}))
        return jobs

    # Backward compatibility: short_video's first job remains video.render.
    # Animation adds explicit reference-frame planning before motion generation.
    for shot in plan.shots:
        if fmt in {ProductionFormat.ANIMATION.value, ProductionFormat.MIXED_MEDIA.value}:
            jobs.append(_job("image.generate", plan, shot=shot, payload={"prompt": _visual_prompt(plan, shot), "purpose": "reference_frame"}))
        jobs.append(_job("video.render", plan, shot=shot, payload={"prompt": _visual_prompt(plan, shot)}))
        if shot.dialogue:
            jobs.append(_job("voice.synthesize", plan, shot=shot, payload={"text": shot.dialogue}))
        if shot.audio_notes:
            jobs.append(_job("audio.sfx.generate", plan, shot=shot, payload={"brief": shot.audio_notes}))

    jobs.append(_job("edit.assemble", plan, payload={"shot_ids": [s.shot_id for s in plan.shots], "deliverables": list(plan.deliverables)}))
    return jobs
