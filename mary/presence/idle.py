"""Zero-cloud idle behavior selection for game-like presence."""
from __future__ import annotations
from dataclasses import dataclass, asdict
import random

@dataclass(frozen=True)
class IdleAction:
    kind:str; name:str; weight:float=1.0; phrase:str=""; sound:str=""
    def to_dict(self): return asdict(self)

DEFAULT_ACTIONS=(
    IdleAction("animation","blink_slow",3.5), IdleAction("animation","look_side",2.8), IdleAction("animation","head_tilt",2.0),
    IdleAction("animation","shift_weight",2.4), IdleAction("animation","stretch_small",1.2), IdleAction("animation","smile_soft",1.5),
    IdleAction("sound","hum_soft",.35,sound="idle_hum.wav"), IdleAction("sound","tiny_chime",.18,sound="idle_chime.wav"),
    IdleAction("phrase","check_in",.08,phrase="Hm? I'm still here."), IdleAction("phrase","thinking",.05,phrase="I was thinking about something."),
)
class IdleBehavior:
    def __init__(self, actions=DEFAULT_ACTIONS, seed=None): self.actions=tuple(actions); self.random=random.Random(seed)
    def choose(self)->IdleAction:
        return self.random.choices(self.actions,weights=[max(.001,a.weight) for a in self.actions],k=1)[0]
