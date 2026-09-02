"""Import creator-scored blind Adapter Lab results into Mary's model lab.

Only numeric creator review scores are aggregated.  The importer never promotes
model output into character canon, memory, preferences, or relationship state.
"""
from __future__ import annotations

import argparse
from collections import defaultdict
import json
from pathlib import Path
from statistics import mean

from mary.core.config import Config
from mary.learning import AdapterEvaluation, AdapterLab


def main() -> int:
    parser = argparse.ArgumentParser(description="Import creator-scored Adapter Lab blind review")
    parser.add_argument("run_dir", help="Adapter Lab run directory containing blind_review.json and blind_key.json")
    args = parser.parse_args()
    run_dir = Path(args.run_dir).expanduser().resolve()
    review = json.loads((run_dir / "blind_review.json").read_text(encoding="utf-8"))
    key = json.loads((run_dir / "blind_key.json").read_text(encoding="utf-8"))
    mapping = {str(item.get("option_id")): str(item.get("config_id")) for item in key if isinstance(item, dict)}

    scores_by_config: dict[str, dict[str, list[float]]] = defaultdict(lambda: defaultdict(list))
    latencies: dict[str, list[float]] = defaultdict(list)
    preferred: dict[str, int] = defaultdict(int)
    reviewed = 0
    for row in review if isinstance(review, list) else []:
        for option in list(row.get("options") or []) if isinstance(row, dict) else []:
            if not isinstance(option, dict):
                continue
            config_id = mapping.get(str(option.get("option_id") or ""), "")
            if not config_id:
                continue
            numeric = False
            for dimension, raw in dict(option.get("scores") or {}).items():
                try:
                    value = float(raw)
                except (TypeError, ValueError):
                    continue
                # Accept convenient 0..1 or 0..10 creator scales.
                if value > 1.0:
                    value /= 10.0
                scores_by_config[config_id][str(dimension)[:80]].append(max(0.0, min(1.0, value)))
                numeric = True
            if numeric:
                reviewed += 1
            try:
                latencies[config_id].append(max(0.0, float(option.get("latency_ms") or 0.0)))
            except (TypeError, ValueError):
                pass
            if bool(option.get("preferred")):
                preferred[config_id] += 1

    config = Config.from_environment()
    lab = AdapterLab(Path(config.paths.data) / "ecosystem" / "model_adapter_lab.json")
    manifest = json.loads((run_dir / "manifest.json").read_text(encoding="utf-8"))
    for raw in list(manifest.get("configurations") or []):
        if not isinstance(raw, dict):
            continue
        config_id = str(raw.get("config_id") or "")
        if config_id and config_id not in lab.configurations:
            # Experiments may use request-local llama.cpp ids instead of a
            # file-backed AdapterSpec, so keep the lab registry descriptive.
            from mary.learning.adapter_lab import AdapterConfiguration, AdapterSpec
            adapters = tuple(
                AdapterSpec(
                    adapter_id=f"server_adapter_{item.get('id')}",
                    base_model=str(raw.get("base_model") or "local"),
                    path_or_repo=f"llama.cpp:id={item.get('id')}",
                    scale=float(item.get("scale", 1.0)),
                    format="llama.cpp_server_slot",
                    license="review separately",
                    purpose="adapter_lab",
                )
                for item in list(raw.get("adapters") or [])
                if isinstance(item, dict)
            )
            lab.register(AdapterConfiguration(
                config_id=config_id,
                base_model=str(raw.get("base_model") or "local"),
                adapters=adapters,
                runtime="llama.cpp",
                notes=str(raw.get("label") or "blind adapter experiment"),
            ))

    imported = 0
    for config_id, dimensions in scores_by_config.items():
        if config_id not in lab.configurations:
            continue
        averaged = {dimension: mean(values) for dimension, values in dimensions.items() if values}
        if preferred[config_id]:
            averaged["creator_preference_rate"] = preferred[config_id] / max(1, len(review))
        lab.record(AdapterEvaluation(
            config_id=config_id,
            scores=averaged,
            latency_ms=mean(latencies[config_id]) if latencies[config_id] else None,
            evaluator="creator_blind_review",
        ))
        imported += 1

    print("MARYV2 ADAPTER LAB REVIEW IMPORT")
    print("=" * 64)
    print(f"Reviewed options with scores: {reviewed}")
    print(f"Configurations imported:     {imported}")
    print(f"Lab: {lab.path}")
    print("Policy: creator evaluation affects the experiment leaderboard only; it is not character/memory authority.")
    return 0 if imported else 2


if __name__ == "__main__":
    raise SystemExit(main())
