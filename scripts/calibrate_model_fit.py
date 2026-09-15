"""Measure a local model role's cold-load memory footprint without private data.

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
from mary.distributed.resource_calibration import measure_provider_fit
from mary.distributed.resource_hint_provenance import (
    VERSION,
    calibration_fingerprint,
    provenance_env_name,
)


_ROLES = ("general", "conversation", "fast", "utility")


def _default_output(role: str) -> Path:
    runtime_root = os.getenv("MARY_RUNTIME_DIR", "").strip()
    filename = f"model_fit_13_58_{role}.json"
    if runtime_root:
        return Path(runtime_root).expanduser() / filename
    return Path.home() / ".maryv2" / filename


def _provider(runtime: str, role: str):
    if runtime == "ollama":
        from mary.desktop.device_node import _ollama_model_for_role
        from mary.llm.providers.ollama import OllamaProvider
        return OllamaProvider(model=_ollama_model_for_role(role))
    if runtime == "llama_cpp":
        from mary.llm.providers.llama_cpp import LlamaCppProvider
        return LlamaCppProvider()
    raise ValueError(f"unsupported runtime: {runtime}")


def _env_name(runtime: str, role: str) -> str:
    prefix = {
        "ollama": "MARY_OLLAMA_RESOURCE_ACCELERATOR_GIB",
        "llama_cpp": "MARY_LLAMA_CPP_RESOURCE_ACCELERATOR_GIB",
    }[runtime]
    return f"{prefix}_{role.upper()}"


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(
        description="Measure one configured local model role's accelerator-memory footprint.",
    )
    parser.add_argument("--runtime", choices=("ollama", "llama_cpp"), default="ollama")
    parser.add_argument("--role", choices=_ROLES, default="general")
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
    provider = _provider(args.runtime, args.role)
    if not provider.is_available():
        print(f"Configured {args.runtime}/{args.role} provider is not reachable on this device.")
        return 2

    benchmark_result, measurement = measure_provider_fit(
        provider,
        lambda: benchmark_local_llm(
            provider,
            repeats=max(1, min(6, int(args.repeats))),
            quality_suite=False,
        ),
        role=args.role,
    )
    fit = dict(measurement or {})
    provenance = calibration_fingerprint(
        runtime=args.runtime,
        role=args.role,
        model=str(fit.get("model") or provider.model_name() or ""),
        num_ctx=int(fit.get("num_ctx") or getattr(provider, "num_ctx", 0) or 0),
    )
    artifact = {
        "version": VERSION,
        "node_id": node_id_from_environment(),
        "host_fingerprint": host_fingerprint(),
        "measured_at": datetime.now(timezone.utc).isoformat(),
        "runtime": args.runtime,
        "role": args.role,
        "benchmark": dict(benchmark_result or {}),
        "resource_fit": fit,
        "fit_provenance": provenance,
        "authority": "operational_measurement_only",
        "content_retained": False,
        "environment_mutated": False,
    }

    target = (args.output or _default_output(args.role)).expanduser()
    target.parent.mkdir(parents=True, exist_ok=True)
    target.write_text(json.dumps(artifact, indent=2, ensure_ascii=False) + "\n", encoding="utf-8")

    print("MARYV2 13.58 MODEL FIT CALIBRATION")
    print("=" * 64)
    print(f"node:                 {artifact['node_id']}")
    print(f"runtime:              {args.runtime}")
    print(f"role:                 {args.role}")
    print(f"model:                {fit.get('model')}")
    print(f"num_ctx:              {fit.get('num_ctx')}")
    print(f"residency before:     {fit.get('residency_before')}")
    print(f"residency after:      {fit.get('residency_after')}")
    print(f"accelerator source:   {fit.get('accelerator_source')}")
    print(f"observed delta GiB:   {fit.get('accelerator_observed_delta_gib')}")
    print(f"fit-hint status:      {fit.get('fit_hint_status')}")
    suggested = fit.get("suggested_accelerator_gib")
    if fit.get("recommendation_supported_by_measurement") and suggested is not None:
        print(f"suggested {args.role} fit: {suggested} GiB")
        print(f"optional env setting: {_env_name(args.runtime, args.role)}={suggested}")
        print(f"provenance setting:   {provenance_env_name(args.runtime, args.role)}={provenance}")
        print("scope:                 measured role/model/context only; remeasure after changes")
        print("note:                  both values are operator-applied; nothing is changed automatically")
    else:
        print(f"suggested {args.role} fit: none — do not guess; rerun from a verified cold model state")
    print(f"artifact:              {target}")
    print("authority:             operational measurement only; not Mary memory/state")
    if args.print_json:
        print(json.dumps(artifact, indent=2, ensure_ascii=False))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
