"""Deterministic verifier for MaryV2 12.12 Cognitive Character Runtime."""
from __future__ import annotations

from pathlib import Path
import json

from mary.mind.behavior import CharacterBehaviorEngine
from mary.mind.local_models import OllamaModelLab
from mary.mind.reservoir import CognitiveReservoir, ReservoirRecord
from mary.expression.director import ExpressionDirector
from mary.runtime.release import APP_VERSION, DESKTOP_PHASE

ROOT = Path(__file__).resolve().parents[1]


def check(condition: bool, message: str) -> bool:
    print(f"[{'OK' if condition else 'FAIL'}] {message}")
    return bool(condition)


def main() -> int:
    print("=" * 76)
    print("MARYV2 12.12 COGNITIVE RESERVOIR + CHARACTER RUNTIME")
    print("=" * 76)
    checks: list[bool] = []
    checks.append(check(APP_VERSION.startswith("12.12."), f"software version preserves 12.12 line ({APP_VERSION})"))
    checks.append(check(DESKTOP_PHASE == "cognitive-reservoir-character-runtime", "desktop phase is cognitive character runtime"))

    required = [
        "mary/mind/character_mind.py",
        "mary/mind/reservoir.py",
        "mary/mind/hot_state.py",
        "mary/mind/dialogue_policy.py",
        "mary/mind/local_composer.py",
        "mary/mind/behavior.py",
        "mary/mind/local_models.py",
        "mary/mind/embeddings.py",
        "mary/expression/director.py",
        "mary/expression/delivery_plan.py",
        "scripts/benchmark_local_models.py",
        "scripts/select_local_dialogue_model_windows.ps1",
        "desktop/src/main.js",
        "START_HERE_12_12.md",
    ]
    for rel in required:
        checks.append(check((ROOT / rel).exists(), f"12.12 surface exists: {rel}"))

    reservoir = CognitiveReservoir.in_memory()
    reservoir.upsert(ReservoirRecord(
        record_id="verify:creator-color",
        kind="creator_preference",
        subject="creator",
        predicate="favorite_color",
        content="The creator's favorite color is blue.",
        source="verifier",
        authority="creator_explicit",
        confidence=1.0,
    ))
    hit = reservoir.search("favorite color", limit=1)
    checks.append(check(bool(hit and hit[0].authority == "creator_explicit"), "reservoir retrieval retains provenance/authority"))
    status = reservoir.status()
    checks.append(check(status.get("records") == 1 and "max_megabytes" in status, "reservoir is bounded and inspectable"))
    reservoir.close()

    catalog = OllamaModelLab.catalog()
    names = {item.get("model") for item in catalog}
    checks.append(check({"qwen3:1.7b", "llama3.2:3b", "gemma3:1b", "phi4-mini", "qwen3:4b", "nomic-embed-text"}.issubset(names), "hardware-conscious local model lab is installed"))

    behavior = CharacterBehaviorEngine(seed=4).idle_decision(
        focus_active=True,
        pending_thoughts=[],
        idle_action={"kind": "animation", "name": "look_side"},
    )
    checks.append(check(behavior.action.value == "idle_animation" and behavior.payload.get("focus_quiet") is True, "focus keeps autonomous presence nonverbal"))

    html = (ROOT / "desktop/index.html").read_text(encoding="utf-8")
    js = (ROOT / "desktop/src/main.js").read_text(encoding="utf-8")
    checks.append(check('data-screen="mind"' in html and "function renderMind()" in js, "Local Mind workspace is visible"))
    checks.append(check("currentDeliveryPlan" in js and "gesture_energy" in js, "voice delivery plan also drives avatar motion"))

    package = json.loads((ROOT / "PACKAGE_INFO.json").read_text(encoding="utf-8"))
    checks.append(check(str(package.get("version") or "").startswith("12.12."), "package metadata matches 12.12"))

    ok = all(checks)
    print("=" * 76)
    print("MARYV2 12.12 CHARACTER RUNTIME VERIFIED" if ok else "MARYV2 12.12 VERIFICATION FAILED")
    return 0 if ok else 1


if __name__ == "__main__":
    raise SystemExit(main())
