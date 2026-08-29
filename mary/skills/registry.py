"""Capability registry: one Mary, many explicitly enabled workspaces/tools."""
from __future__ import annotations
import os
from dataclasses import dataclass, asdict
from typing import Any

@dataclass(frozen=True)
class Skill:
    key:str; label:str; category:str; default_enabled:bool=True; external:bool=False; description:str=""
    def to_dict(self,enabled:bool): return {**asdict(self),"enabled":enabled}

SKILLS=(
 Skill("companion","Companion","core",True,False,"Chat, memory, mood, relationship and avatar."),
 Skill("studio","Creative Studio","create",True,False,"Projects, chapters, references and creative-app handoffs."),
 Skill("production","Production Studio","create",True,False,"Provider-neutral character, storyboard, shot, voice, render, edit and publishing plans."),
 Skill("study","Study Partner","productivity",True,False,"Persistent study projects and spaced repetition."),
 Skill("focus","Focus With Mary","productivity",True,False,"Quiet co-working and timed focus blocks."),
 Skill("command","Command Center","productivity",True,False,"Tasks, projects, goals, waiting threads and ideas."),
 Skill("search","Find That Thing","productivity",True,False,"Bounded local search over approved roots."),
 Skill("research","Research Notebook","knowledge",True,False,"Persistent research threads and evidence notes."),
 Skill("arcade","Mary Arcade","entertainment",True,False,"Small local games and playful activities."),
 Skill("presence","Presence","presence",True,False,"Initiative, idle behavior and typed live context."),
 Skill("twitch","Twitch","external",False,True,"Approved-channel Twitch presence."),
 Skill("obs","OBS","external",False,True,"OBS WebSocket stream-state integration."),
 Skill("vision","Visual Context","external",False,True,"Explicit opt-in screen/window observations."),
 Skill("renpy","Ren'Py","external",False,True,"Visual-novel export/integration."),
 Skill("expert","OpenAI Expert","external",False,True,"Explicit paid expert consultation."),
)
class SkillRegistry:
    def __init__(self):
        self.skills={s.key:s for s in SKILLS}
    def enabled(self,key:str)->bool:
        skill=self.skills.get(key)
        if skill is None:return False
        env=f"MARY_SKILL_{key.upper()}"
        raw=os.getenv(env,"").strip().lower()
        if raw:return raw in {"1","true","yes","on"}
        return skill.default_enabled
    def snapshot(self)->list[dict[str,Any]]: return [s.to_dict(self.enabled(s.key)) for s in self.skills.values()]
