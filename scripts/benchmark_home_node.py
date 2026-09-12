"""Benchmark one Mary capability node without exposing private data.

The runner uses only synthetic/local reference work. Optional local-LLM probes
send a fixed benchmark prompt and never inspect Mary memory, chat, files, or
credentials.
"""
from __future__ import annotations

import argparse
import json
import os
from pathlib import Path

from dotenv import load_dotenv

from mary.distributed.benchmarking import build_profile, save_profile


def _default_output() -> Path:
    configured = os.getenv("MARY_NODE_BENCHMARK_PROFILE", "").strip()
    if configured:
        return Path(configured).expanduser()
    runtime_root = os.getenv("MARY_RUNTIME_DIR", "").strip()
    if runtime_root:
        return Path(runtime_root).expanduser() / "node_benchmark_13_11.json"
    return Path.home() / ".maryv2" / "node_benchmark_13_11.json"


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description="Benchmark this Mary capability node.")
    parser.add_argument("--local-llm", action="store_true", help="Also benchmark reachable Ollama/llama.cpp using a fixed synthetic prompt.")
    parser.add_argument("--repeats", type=int, default=2, help="Benchmark repetitions (1-6).")
    parser.add_argument("--output", type=Path, default=None, help="Profile destination outside the repository.")
    parser.add_argument("--print-json", action="store_true", help="Print the sanitized profile JSON after saving.")
    args = parser.parse_args(argv)
    load_dotenv()

    profile = build_profile(
        include_local_llm=bool(args.local_llm),
        repeats=max(1, min(6, int(args.repeats))),
    )
    target = save_profile(profile, args.output or _default_output())

    print("MARYV2 13.11 NODE BENCHMARK")
    print("=" * 64)
    print(f"node:             {profile.get('node_id')}")
    resource = dict(profile.get("resource") or {})
    print(f"platform:         {resource.get('platform')} / {resource.get('machine')}")
    print(f"cpu threads:      {resource.get('cpu_count')}")
    print(f"memory GiB:       {resource.get('memory_gib', 'unknown')}")
    print(f"apple silicon:    {resource.get('apple_silicon', False)}")
    print(f"ollama detected:  {resource.get('ollama_available', False)}")
    print(f"llama.cpp found:  {resource.get('llama_cpp_available', False)}")
    print(f"whisper.cpp found:{resource.get('whisper_cpp_available', False)}")
    cpu = dict(profile.get("cpu_reference") or {})
    print(f"cpu ref median:   {cpu.get('median_latency_ms')} ms")
    for capability, result in dict(profile.get("capabilities") or {}).items():
        values = dict(result or {})
        print(
            f"{capability}: median={values.get('median_latency_ms')}ms "
            f"success={values.get('success_rate')} throughput={values.get('throughput_tokens_per_second')} tok/s"
        )
    print(f"profile:          {target}")
    print("authority:        operational benchmark only; not Mary memory/state")
    if args.print_json:
        print(json.dumps(profile, indent=2, ensure_ascii=False))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
