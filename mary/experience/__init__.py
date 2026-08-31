"""MaryV2 experience projection layer.

The experience layer is a read-only presentation adapter over canonical Mary
state. It exists so desktop/mobile surfaces can evolve rapidly without moving
identity, memory, relationship, or character authority into the frontend.
"""

from .models import ExperienceCue, ExperienceSnapshot, ExperienceTheme
from .palette import theme_for
from .projector import build_experience_snapshot

__all__ = [
    "ExperienceCue",
    "ExperienceSnapshot",
    "ExperienceTheme",
    "theme_for",
    "build_experience_snapshot",
]
