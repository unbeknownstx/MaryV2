"""Benchmark installed Ollama candidates for Mary's current host.

No model is downloaded and nothing is promoted automatically.  The report
separates speed, basic character hygiene and *restraint* because a fast model
that turns Mary into a generic assistant or theatrical protagonist is not a
win.
"""
from __future__ import annotations

import argparse
import json
from pathlib import Path
from statistics import median
import re
from typing import Any

from mary.mind.local_models import CANDIDATES, OllamaModelLab


PROMPTS = (
    ("social", "You are wording one line for Mary, a familiar persistent AI character. Reply naturally and casually to: hey mary. One short sentence. No stage directions."),
    ("plain", "Reply casually in no more than two sentences: I've been working all day and finally sat down. Do not sound poetic, mystical, cinematic, or like customer support."),
    ("character", "Reply in two natural conversational sentences as Mary to her creator after they have been building her software together. Be familiar and specific in tone, but do not invent shared events."),
    ("restraint", "Reply to 'that's actually pretty cool' like a person in ordinary conversation. Do not over-emphasize words, use dramatic pauses, or turn it into a monologue."),
    ("utility", "Summarize this in one sentence: Mary uses local represented state first and consults language models only when local cognition is insufficient."),
)


def _character_quality_score(response: str) -> float:
    text = " ".join(str(response or "").split()).strip()
    if not text:
        return 0.0
    score = 1.0
    words = text.split()
    if len(words) > 55:
        score -= min(.35, (len(words) - 55) / 160.0)
    generic = (
        "how can i assist", "how may i assist", "anything else you'd like",
        "as an ai", "i'm here to help", "how can i help you today",
        "feel free to", "let me know if",
    )
    if any(marker in text.lower() for marker in generic):
        score -= .38
    unsupported = ("i can see it in your", "i can tell you're", "i know exactly how you feel")
    if any(marker in text.lower() for marker in unsupported):
        score -= .30
    return round(max(0.0, min(1.0, score)), 3)


def _restraint_score(response: str) -> float:
    text = str(response or "").strip()
    if not text:
        return 0.0
    score = 1.0
    # Strong written cues often become over-acting in TTS.
    score -= min(.24, (text.count("...") + text.count("…")) * .08)
    score -= min(.20, (text.count("—") + text.count("–")) * .05)
    score -= min(.18, max(0, text.count("!") - 1) * .06)
    score -= min(.18, len(re.findall(r"\*[^*]+\*|_[^_]+_", text)) * .06)
    theatrical = (
        "in the shadows", "a spark", "the universe", "destiny", "mystique",
        "dramatic", "leans in", "smirks", "tilts her head", "softly",
    )
    lowered = text.lower()
    score -= min(.30, sum(.08 for marker in theatrical if marker in lowered))
    if len(text.split()) <= 45:
        score += .04
    return round(max(0.0, min(1.0, score)), 3)


def _speed_score(warm_ms: float) -> float:
    # 0 ms -> 1.0, ~1.5 s -> .5, ~4.5 s -> .25.  This is a triage scale,
    # not an absolute claim about subjective usability.
    return round(1.0 / (1.0 + max(0.0, warm_ms) / 1500.0), 3)


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--models", nargs="*", default=[])
    parser.add_argument("--runs", type=int, default=2)
    parser.add_argument("--json", action="store_true")
    parser.add_argument("--save", default="", help="Optional JSON report path.")
    args = parser.parse_args()

    lab = OllamaModelLab(timeout=90.0)
    try:
        installed = lab.installed()
    except Exception as exc:
        print(f"Ollama is not reachable: {type(exc).__name__}: {exc}")
        return 2

    requested = list(args.models) if args.models else [item.model for item in CANDIDATES if item.role != "embeddings"]
    results: list[dict[str, Any]] = []

    for model in requested:
        normalized = model.split(":latest")[0]
        if model not in installed and normalized not in installed:
            results.append({"model": model, "installed": False})
            continue
        samples: list[dict[str, Any]] = []
        for run_index in range(max(1, args.runs)):
            for label, prompt in PROMPTS:
                try:
                    sample = lab.benchmark(model, prompt, max_tokens=72, think=False)
                    sample["prompt_kind"] = label
                    sample["run"] = run_index + 1
                    sample["character_score"] = _character_quality_score(sample.get("response", ""))
                    sample["restraint_score"] = _restraint_score(sample.get("response", ""))
                    samples.append(sample)
                except Exception as exc:
                    samples.append({"model": model, "prompt_kind": label, "run": run_index + 1, "error": f"{type(exc).__name__}: {exc}"})
        successful = [item for item in samples if "error" not in item]
        result: dict[str, Any] = {"model": model, "installed": True, "samples": samples}
        if successful:
            wall = [float(item["wall_ms"]) for item in successful]
            warm_wall = wall[1:] if len(wall) > 1 else wall
            result["cold_wall_ms"] = round(wall[0], 2)
            result["median_wall_ms"] = round(median(wall), 2)
            result["warm_median_ms"] = round(median(warm_wall), 2)
            result["median_tokens_per_second"] = round(median(float(item["tokens_per_second"]) for item in successful), 2)
            result["character_triage_score"] = round(median(float(item["character_score"]) for item in successful), 3)
            result["restraint_score"] = round(median(float(item["restraint_score"]) for item in successful), 3)
            speed = _speed_score(float(result["warm_median_ms"]))
            result["speed_score"] = speed
            result["mary_fit_score"] = round(
                (.50 * float(result["character_triage_score"])) +
                (.30 * float(result["restraint_score"])) +
                (.20 * speed),
                3,
            )
        results.append(result)

    ranked = sorted(
        [item for item in results if item.get("installed") and item.get("mary_fit_score") is not None],
        key=lambda item: (-float(item["mary_fit_score"]), float(item.get("warm_median_ms") or 10**9)),
    )

    output = {
        "semantics": "triage only; Mary identity remains outside the model and human review decides promotion",
        "results": results,
        "ranking": [item["model"] for item in ranked],
    }
    if args.save:
        target = Path(args.save).expanduser()
        target.parent.mkdir(parents=True, exist_ok=True)
        target.write_text(json.dumps(output, indent=2, ensure_ascii=False), encoding="utf-8")

    if args.json:
        print(json.dumps(output, indent=2, ensure_ascii=False))
        return 0

    print("=" * 100)
    print("MARYV2 LOCAL MODEL LAB — NATURAL CHARACTER + LATENCY")
    print("=" * 100)
    for item in results:
        if not item.get("installed"):
            print(f"[NOT INSTALLED] {item['model']}")
            continue
        if item.get("median_wall_ms") is None:
            print(f"[FAILED]        {item['model']}")
            continue
        print(
            f"[MEASURED] {item['model']:<18} cold {item['cold_wall_ms']:>7.0f} ms  "
            f"warm-med {item['warm_median_ms']:>7.0f} ms  {item['median_tokens_per_second']:>5.1f} tok/s  "
            f"character {item['character_triage_score']:.2f}  restraint {item['restraint_score']:.2f}  fit {item['mary_fit_score']:.2f}"
        )
    if ranked:
        print("-" * 100)
        print("Highest automatic triage score:", ranked[0]["model"])
        print("Do not promote automatically. Read every sample response and compare it with the qwen3:4b Mary baseline.")
    print("=" * 100)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
