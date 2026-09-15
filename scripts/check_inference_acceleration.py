"""Inspect Mary's local inference-acceleration readiness without starting services."""
from __future__ import annotations

import argparse
import json

from mary.distributed.local_inference_readiness import local_inference_status


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description="Inspect local inference/MTP readiness.")
    parser.add_argument("--model", default="", help="Local model/checkpoint name to evaluate.")
    parser.add_argument(
        "--runtime",
        default="",
        choices=["", "ollama", "llama_cpp", "mlx", "vllm"],
        help="Runtime serving the model.",
    )
    parser.add_argument("--json", action="store_true", help="Print full sanitized JSON.")
    args = parser.parse_args(argv)

    status = local_inference_status(
        model=args.model or None,
        runtime=args.runtime or None,
    )
    acceleration = dict(status.get("inference_acceleration") or {})
    candidate = dict(acceleration.get("candidate") or {})

    if args.json:
        print(json.dumps(status, indent=2, ensure_ascii=False))
        return 0

    print("MARYV2 13.24 LOCAL INFERENCE ACCELERATION")
    print("=" * 68)
    print(f"Ollama configured:     {status.get('ollama_configured')}")
    print(f"llama.cpp Python:      {status.get('llama_cpp_python_installed')}")
    print(f"MLX-LM installed:      {status.get('mlx_lm_installed')}")
    print(f"vLLM installed:        {status.get('vllm_installed')}")
    print(f"Acceleration mode:     {acceleration.get('mode')}")
    print(f"Speculative tokens:    {acceleration.get('speculative_tokens')}")
    print(f"Candidate method:      {candidate.get('method')}")
    print(f"Candidate state:       {candidate.get('state')}")
    print(f"Reason:                {candidate.get('reason')}")
    print("Authority:             diagnostics only; benchmark required before promotion")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
