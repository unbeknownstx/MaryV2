"""Provider-neutral creative production planning for MaryV2.

Turns Mary's existing character/performance intelligence into durable *project
artifacts*, never identity state. Rendering/publishing remain explicit
capabilities and require their normal permission boundaries.
"""
from __future__ import annotations
from dataclasses import asdict, dataclass, field
from enum import Enum
from hashlib import sha256
from typing import Any, Iterable
from uuid import uuid4


class ProductionStage(str, Enum):
    IDEA="idea"; SCRIPT="script"; STORYBOARD="storyboard"; ASSETS="assets"; RENDER="render"; EDIT="edit"; REVIEW="review"; PUBLISH="publish"


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
    def to_dict(self)->dict[str,Any]: return asdict(self)


@dataclass(frozen=True)
class Shot:
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
    def to_dict(self)->dict[str,Any]: return asdict(self)


@dataclass(frozen=True)
class ProductionPlan:
    production_id: str
    title: str
    objective: str
    format: str
    aspect_ratio: str
    target_seconds: int
    stage: str
    characters: tuple[CharacterAnchor,...]
    shots: tuple[Shot,...]
    deliverables: tuple[str,...]
    provider_preferences: dict[str,str] = field(default_factory=dict)
    approval_gates: tuple[str,...] = ("external_render", "filesystem_write", "publish")
    provenance: str = "creator_directed"
    version: str = "1"
    def to_dict(self)->dict[str,Any]:
        d=asdict(self); d["characters"]=[x.to_dict() for x in self.characters]; d["shots"]=[x.to_dict() for x in self.shots]; return d
    @property
    def fingerprint(self)->str:
        core=f"{self.title}|{self.objective}|{self.format}|{self.target_seconds}|"+"|".join(s.action for s in self.shots)
        return sha256(core.encode()).hexdigest()[:16]


def build_production_plan(*, title:str, objective:str, shots:Iterable[Shot], characters:Iterable[CharacterAnchor]=(), format:str="short_video", aspect_ratio:str="9:16", target_seconds:int=30, deliverables:Iterable[str]=("master_video","thumbnail","caption"), provider_preferences:dict[str,str]|None=None)->ProductionPlan:
    title=" ".join(str(title).split())[:160]; objective=" ".join(str(objective).split())[:4000]
    if not title or not objective: raise ValueError("title and objective are required")
    shot_tuple=tuple(shots)
    if not shot_tuple or len(shot_tuple)>64: raise ValueError("production requires 1..64 shots")
    seconds=max(1,min(int(target_seconds),3600))
    return ProductionPlan(str(uuid4()),title,objective,str(format)[:64],str(aspect_ratio)[:16],seconds,ProductionStage.STORYBOARD.value,tuple(characters)[:16],shot_tuple,tuple(str(x)[:80] for x in deliverables)[:16],dict(provider_preferences or {}))


def capability_jobs(plan:ProductionPlan)->list[dict[str,Any]]:
    """Translate one plan into bounded jobs; this does not execute anything."""
    jobs=[]
    for shot in plan.shots:
        jobs.append({"kind":"video.render","production_id":plan.production_id,"shot_id":shot.shot_id,"prompt":{"action":shot.action,"environment":shot.environment,"camera":shot.camera,"expression":shot.expression,"continuity":list(shot.continuity)},"requires_approval":True})
        if shot.dialogue:
            jobs.append({"kind":"voice.synthesize","production_id":plan.production_id,"shot_id":shot.shot_id,"text":shot.dialogue,"requires_approval":True})
    jobs.append({"kind":"edit.assemble","production_id":plan.production_id,"shot_ids":[s.shot_id for s in plan.shots],"requires_approval":True})
    return jobs
