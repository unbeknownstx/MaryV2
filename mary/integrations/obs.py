"""OBS WebSocket configuration boundary. External connection is opt-in."""
from __future__ import annotations
import os
from dataclasses import dataclass, asdict

@dataclass(frozen=True)
class ObsPolicy:
    enabled: bool; host: str; port: int; allow_scene_switch: bool=False
    def to_dict(self): return asdict(self)

def obs_policy_from_environment()->ObsPolicy:
    enabled=os.getenv("MARY_SKILL_OBS","").strip().lower() in {"1","true","yes","on"}
    return ObsPolicy(enabled,os.getenv("MARY_OBS_HOST","127.0.0.1"),int(os.getenv("MARY_OBS_PORT","4455") or 4455),os.getenv("MARY_OBS_ALLOW_SCENE_SWITCH","").strip().lower() in {"1","true","yes","on"})
