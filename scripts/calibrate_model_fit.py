"""Measure a local model's cold-load memory footprint without private data.

This explicit operator tool reuses Mary's fixed synthetic benchmark prompt and
writes a disposable operational calibration artifact. It never edits .env,
node permissions, Mary memory, or Core state.
"""
from __future__ import annotations

import argparse
from datetime import datetime, timezone
import json
import os
from pathlib import Path

from dotenv import load_dotenv

from mary.distributed.benchmarking import (
    benchmark_local_llm,
    host_fingerprint,
    node_id_from_environment,
)
from mary.distributed.hardware_profiles import apply_hardware_profile, available_hardware_profiles
from mary.distributed.resource_calibration import REVISION, measure_provider_fit


def _default_output() -> Path:
    runtime_root = os.getenv("MARY_RUNTIME_DIR", "").strip()
    if runtime_root:
        return Path(runtime_root).expanduser() / "model_fit_13_56.json"
    return Path.home() / ".maryv2" / "model_fit_13_56.json"


def _provider(runtime: str):
    if runtime == "ollama":
        from mary.llm.providers.ollama import OllamaProvider
        return OllamaProvider()
    if runtime == "llama_cpp":
        from mary.llm.providers.llama_cpp import LlamaCppProvider
        return LlamaCppProvider()
    raise ValueError(f"unsupported runtime: {runtime}")


def _env_name(runtime: str) -> str:
    return {
        "ollama": "MARY_OLLAMA_RESOURCE_ACCELERATOR_GIB_GENERAL",
        "llama_cpp": "MARY_LLAMA_CPP_RESOURCE_ACCELERATOR_GIB_GENERAL",
    }[runtime]


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(
        description="Measure the configured general local model's accelerator-memory footprint.",
    )
    parser.add_argument("--runtime", choices=("ollama", "llama_cpp"), default="ollama")
    parser.add_argument(
        "--hardware-profile",
        choices=available_hardware_profiles(),
        default=None,
        help="Apply the same device-local inference safety profile used by the home node.",
    )
    parser.add_argument("--repeats", type=int, default=2, help="Synthetic benchmark repetitions (1-6).")
    parser.add_argument("--output", type=Path, default=None, help="Calibration artifact destination outside source.")
    parser.add_argument("--print-json", action="store_true", help="Print the sanitized artifact JSON.")
    args = parser.parse_args(argv)

    load_dotenv()
    apply_hardware_profile(args.hardware_profile)
    provider = _provider(args.runtime)
    if not provider.is_available():
        print(f"Configured {args.runtime} provider is not reachable on this device.")
        return 2

    benchmark_result, measurement = measure_provider_fit(
        provider,
        lambda: benchmark_local_llm(
            provider,
            repeats=max(1, min(6, int(args.repeats))),
            quality_suite=False,
        ),
    )
    artifact = {
        "version": REVISION,
        "node_id": node_id_from_environment(),
        "host_fingerprint": host_fingerprint(),
        "measured_at": datetime.now(timezone.utc).isoformat(),
        "runtime": args.runtime,
        "role": "general",
        "benchmark": dict(benchmark_result or {}),
        "resource_fit": dict(measurement or {}),
        "authority": "operational_measurement_only",
        "content_retained": False,
        "environment_mutated": False,
    }

    target = (args.output or _default_output()).expanduser()
    target.parent.mkdir(parents=True, exist_ok=True)
    target.write_text(json.dumps(artifact, indent=2, ensure_ascii=False) + "\n", encoding="utf-8")

    fit = artifact["resource_fit"]
    print("MARYV2 13.56 MODEL FIT CALIBRATION")
    print("=" * 64)
    print(f"node:                 {artifact['node_id']}")
    print(f"runtime:              {args.runtime}")
    print(f"model:                {fit.get('model')}")
    print(f"num_ctx:              {fit.get('num_ctx')}")
    print(f"residency before:     {fit.get('residency_before')}")
    print(f"residency after:      {fit.get('residency_after')}")
    print(f"accelerator source:   {fit.get('accelerator_source')}")
    print(f"observed delta GiB:   {fit.get('accelerator_observed_delta_gib')}")
    print(f"fit-hint status:      {fit.get('fit_hint_status')}")
    suggested = fit.get("suggested_accelerator_gib_general")
    if fit.get("recommendation_supported_by_measurement") and suggested is not None:
        print(f"suggested general fit:{suggested} GiB")
        print(f"optional env setting: {_env_name(args.runtime)}={suggested}")
        print("scope:                 measured model/context only; remeasure after changes")
        print("note:                  recommendation is not applied automatically")
    else:
        print("suggested general fit:none — do not guess; rerun from a verified cold model state")
    print(f"artifact:              {target}")
    print("authority:             operational measurement only; not Mary memory/state")
    if args.print_json:
        print(json.dumps(artifact, indent=2, ensure_ascii=False))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
