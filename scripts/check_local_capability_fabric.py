"""Read-only diagnostic for Mary's mined local capability fabric."""
from __future__ import annotations

import argparse
import json

from dotenv import load_dotenv

from mary.distributed.creative_runtime import creative_runtime_catalog
from mary.distributed.local_inference_readiness import local_inference_status


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description="Inspect Mary's local runtime/creative capability fabric.")
    parser.add_argument("--runtime", default=None, help="Runtime to evaluate for acceleration (ollama, llama.cpp, jan, vllm).")
    parser.add_argument("--model", default=None, help="Model/checkpoint label for acceleration diagnostics.")
    parser.add_argument("--gguf-nextn", type=int, default=None, help="Explicit GGUF nextn_predict_layers metadata when known.")
    parser.add_argument("--json", action="store_true", help="Print full diagnostics JSON.")
    args = parser.parse_args(argv)
    load_dotenv()

    inference = local_inference_status(
        runtime=args.runtime,
        model=args.model,
        gguf_nextn_predict_layers=args.gguf_nextn,
    )
    creative = creative_runtime_catalog()
    payload = {
        "version": "13.28",
        "inference": inference,
        "creative": creative,
        "authority": "diagnostics_only",
    }

    if args.json:
        print(json.dumps(payload, indent=2, ensure_ascii=False))
        return 0

    print("MARYV2 LOCAL CAPABILITY FABRIC")
    print("=" * 68)
    print("Inference runtimes:")
    for item in inference.get("runtime_catalog", []):
        print(
            f"  - {item.get('name', 'unknown'):<12} "
            f"configured={str(item.get('configured', False)).lower():<5} "
            f"protocol={item.get('protocol', 'unknown')}"
        )
    acceleration = dict(inference.get("inference_acceleration") or {})
    candidate = dict(acceleration.get("candidate") or {})
    if args.runtime or args.model:
        print("Acceleration candidate:")
        print(f"  method:    {candidate.get('method')}")
        print(f"  state:     {candidate.get('state')}")
        print(f"  evidence:  {candidate.get('checkpoint_evidence')}")
        print(f"  reason:    {candidate.get('reason')}")
    print("Creative runtimes:")
    for item in creative:
        print(
            f"  - {item.get('name', 'unknown'):<16} "
            f"configured={str(item.get('configured', False)).lower():<5} "
            f"ops={','.join(item.get('operations') or [])}"
        )
    print("authority: diagnostics only; Core identity/permissions unchanged")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
