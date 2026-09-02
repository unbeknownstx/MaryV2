"""Run a local llama.cpp Mary/LoRA comparison without touching canonical state."""
from __future__ import annotations

import argparse
import json
from pathlib import Path

from mary.core.config import Config
from mary.character.sourcebook import CharacterSourcebook
from mary.learning.adapter_runner import (
    AdapterExperimentRunner,
    AdapterMix,
    ExperimentConfiguration,
)
from mary.llm.providers.llama_cpp import LlamaCppProvider


def _configuration(value: str, *, default_model: str) -> ExperimentConfiguration:
    """Parse CONFIG_ID|LABEL|MODEL|ID:SCALE,ID:SCALE (adapters optional)."""
    parts = str(value or "").split("|", 3)
    if len(parts) < 2:
        raise argparse.ArgumentTypeError("config must be CONFIG_ID|LABEL[|MODEL[|ID:SCALE,...]]")
    config_id, label = parts[0].strip(), parts[1].strip()
    model = parts[2].strip() if len(parts) >= 3 and parts[2].strip() else default_model
    adapters: list[AdapterMix] = []
    if len(parts) == 4 and parts[3].strip():
        for raw in parts[3].split(","):
            adapter_id, _, scale = raw.strip().partition(":")
            try:
                adapters.append(AdapterMix(int(adapter_id), float(scale or "1")))
            except ValueError as exc:
                raise argparse.ArgumentTypeError(f"invalid adapter scale: {raw}") from exc
    return ExperimentConfiguration(config_id=config_id, label=label, base_model=model or "local", adapters=tuple(adapters))


def main() -> int:
    parser = argparse.ArgumentParser(description="Blind A/B Mary character tests for local llama.cpp + LoRAs")
    parser.add_argument("--eval-file", default="mary_eval_suite_alpha.jsonl")
    parser.add_argument("--base-url", default="")
    parser.add_argument("--model", default="")
    parser.add_argument("--limit", type=int, default=0)
    parser.add_argument("--seed", type=int, default=1337)
    parser.add_argument("--summarize-run", default="", help="Aggregate creator scores already entered into an existing blind_review.json and exit")
    parser.add_argument(
        "--config",
        action="append",
        default=[],
        help="CONFIG_ID|LABEL[|MODEL[|ID:SCALE,...]]; repeat for A/B configurations",
    )
    args = parser.parse_args()

    if args.summarize_run:
        summary = AdapterExperimentRunner.summarize_blind_review(args.summarize_run)
        print("MARYV2 ADAPTER LAB CREATOR REVIEW")
        print("=" * 64)
        print(json.dumps(summary, indent=2, ensure_ascii=False))
        return 0

    config = Config.from_environment()
    provider = LlamaCppProvider(model=args.model or None, base_url=args.base_url or None)
    if not provider.is_available():
        print("Adapter Lab: local llama.cpp is not available/enabled.")
        print("Start llama-server with the desired base and --lora adapters, then set MARY_LLAMA_CPP_ENABLED=true.")
        return 2

    experiment_configs = [
        _configuration(item, default_model=args.model or provider.model_name()) for item in args.config
    ]
    if not experiment_configs:
        experiment_configs = [
            ExperimentConfiguration(config_id="base", label="Base model", base_model=args.model or provider.model_name())
        ]
    cases = AdapterExperimentRunner.load_cases(args.eval_file, limit=args.limit or None)
    output_root = Path(config.paths.data) / "training" / "adapter_lab_runs"
    sourcebook = CharacterSourcebook.from_environment(root=Path(config.paths.root))
    runner = AdapterExperimentRunner(provider, output_root=output_root, sourcebook=sourcebook)
    summary = runner.run(cases, experiment_configs, seed=args.seed)

    print("MARYV2 ADAPTER LAB")
    print("=" * 64)
    print(json.dumps(summary.to_dict(), indent=2))
    print("automatic_review.json contains only explicit regression checks; it is not a Mary-likeness judge.")
    print("Review blind_review.json before opening blind_key.json, then run --summarize-run on the run folder.")
    print("Policy: results are experiment artifacts only; no output becomes memory/canon automatically.")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
