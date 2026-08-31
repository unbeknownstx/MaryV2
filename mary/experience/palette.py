"""MaryV2 experience palettes.

The palette follows the existing Mary art direction: dark navy/black, magenta,
purple, electric cyan, glass HUDs, and subtle state-dependent shifts.
"""

from __future__ import annotations

from .models import ExperienceTheme


_THEMES: dict[str, ExperienceTheme] = {
    "mary": ExperienceTheme("mary", "#ff5aaa", "#8f78ff", "#5fe7ff", "#090b1c", "#f7f2ff"),
    "calm": ExperienceTheme("calm", "#a986ff", "#5ac8ff", "#67f1d1", "#080b1c", "#f4f4ff"),
    "bright": ExperienceTheme("bright", "#ff67b8", "#7d8cff", "#74f0ff", "#0b0b20", "#fff7fc"),
    "focused": ExperienceTheme("focused", "#6bdcff", "#7e8cff", "#b47cff", "#070d1e", "#f0f8ff"),
    "serious": ExperienceTheme("serious", "#f2759d", "#8167d8", "#79b9ff", "#090914", "#f8eef3"),
    "soft": ExperienceTheme("soft", "#db8eff", "#7bbcff", "#f4a8d4", "#0b0a1b", "#fff5fb"),
}


def theme_for(*, mood: str = "", interaction_state: str = "", energy: str = "") -> ExperienceTheme:
    mood_key = str(mood or "").strip().lower()
    state_key = str(interaction_state or "").strip().lower()
    energy_key = str(energy or "").strip().lower()

    if state_key in {"thinking", "responding", "transcribing"} or energy_key in {"focused", "locked in"}:
        return _THEMES["focused"]
    if mood_key in {"angry", "firm", "serious", "hurt"}:
        return _THEMES["serious"]
    if mood_key in {"sad", "soft", "tender", "shy"}:
        return _THEMES["soft"]
    if mood_key in {"happy", "excited", "amused", "playful", "flirty"}:
        return _THEMES["bright"]
    if energy_key in {"calm", "low", "tired", "exhausted"}:
        return _THEMES["calm"]
    return _THEMES["mary"]
