"""Zero-cloud idle behavior selection for game-like presence.

Idle behavior is presentation, not autobiography.  It can animate Mary, play a
small local sound, or perform a tiny grounded check-in.  It must never invent a
private thought merely to make the character look alive.
"""
from __future__ import annotations

from dataclasses import asdict, dataclass
import random


@dataclass(frozen=True)
class IdleAction:
    kind: str
    name: str
    weight: float = 1.0
    phrase: str = ""
    sound: str = ""

    def to_dict(self):
        return asdict(self)


DEFAULT_ACTIONS = (
    IdleAction("animation", "blink_slow", 3.8),
    IdleAction("animation", "look_side", 3.0),
    IdleAction("animation", "glance_down", 2.1),
    IdleAction("animation", "head_tilt", 2.0),
    IdleAction("animation", "shift_weight", 2.6),
    IdleAction("animation", "shoulder_settle", 1.8),
    IdleAction("animation", "stretch_small", 1.1),
    IdleAction("animation", "smile_soft", 1.5),
    IdleAction("sound", "hum_soft", .28, sound="idle_hum.wav"),
    IdleAction("sound", "tiny_chime", .12, sound="idle_chime.wav"),
    # This is grounded only in Mary's actual presence in the running app.  Do
    # not add phrases such as "I was thinking about..." unless a represented
    # PendingThought supports them.
    IdleAction("phrase", "check_in", .055, phrase="Hm? I'm still here."),
)


class IdleBehavior:
    def __init__(self, actions=DEFAULT_ACTIONS, seed=None):
        self.actions = tuple(actions)
        self.random = random.Random(seed)

    def choose(self, allowed_kinds: set[str] | None = None) -> IdleAction:
        actions = self.actions
        if allowed_kinds is not None:
            actions = tuple(action for action in actions if action.kind in allowed_kinds)
        if not actions:
            return IdleAction("animation", "blink_slow", 1.0)
        return self.random.choices(
            actions,
            weights=[max(.001, action.weight) for action in actions],
            k=1,
        )[0]
