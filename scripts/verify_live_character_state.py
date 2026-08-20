"""Verify Mary's display-safe live character state surface."""
from __future__ import annotations

from mary.core.mary import Mary
from mary.runtime.live_state import format_character_card


def check(label: str, condition: bool) -> None:
    if not condition:
        raise AssertionError(label)
    print(f"PASS  {label}")


def main() -> int:
    print("=" * 72)
    print("MARYV2 LIVE CHARACTER STATE")
    print("=" * 72)
    mary = Mary()
    mary.memory.remember("private live-state probe", memory_type="episodic")
    state = mary.live_state(runtime_status="thinking")
    rendered = repr(state)
    card = format_character_card(state)
    check("live state identifies Mary without exposing raw memory bodies", state.get("character", {}).get("name") == "Mary" and "private live-state probe" not in rendered)
    check("represented mood and runtime status are exposed", "mood" in state.get("character", {}) and state.get("character", {}).get("status") == "thinking")
    check("memory counts/capacities are visible", bool(state.get("memory", {}).get("capacities")))
    check("resource counters and privacy policy are visible", "resources" in state and "privacy" in state)
    check("terminal character card renders safely", "MY CHARACTERS" in card and "Mary" in card)
    print("=" * 72)
    print("LIVE CHARACTER STATE VERIFIED")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
