"""Benchmark Mary's actual Railway-Core LLM engines without creating Mary turns.

This creator-authenticated diagnostic calls the bounded ``llm.probe`` runtime
operation. The Core uses its real provider objects, including a connected
Windows Ollama capability node, but does not run MaryApplication and therefore
does not add relationship history, memories, growth evidence, or turn state.
"""
from __future__ import annotations

import argparse
import os
import statistics
import time

from dotenv import load_dotenv

from mary.protocol.client import MaryClient, MaryProtocolError


DEFAULT_PROVIDERS = ("groq", "gemini", "openrouter", "ollama")


def _fmt(value: object, width: int = 8) -> str:
    try:
        return f"{float(value):{width}.1f}"
    except (TypeError, ValueError):
        return f"{'-':>{width}}"


def main() -> int:
    parser = argparse.ArgumentParser(
        description="Benchmark Core-owned free LLM providers without changing canonical Mary state.",
    )
    parser.add_argument(
        "--providers",
        nargs="+",
        default=list(DEFAULT_PROVIDERS),
        choices=list(DEFAULT_PROVIDERS),
    )
    parser.add_argument(
        "--purpose",
        default="conversation",
        choices=("social_instant", "conversation", "general"),
    )
    parser.add_argument(
        "--profile",
        default="conversation",
        choices=("latency", "conversation"),
    )
    parser.add_argument("--samples", type=int, default=3)
    args = parser.parse_args()

    samples = max(1, min(8, int(args.samples)))
    providers = list(dict.fromkeys(args.providers))

    load_dotenv()
    base_url = str(os.getenv("MARY_CORE_URL") or "").strip()
    token = str(os.getenv("MARY_CORE_TOKEN") or "").strip()

    print("MARYV2 RAILWAY-CORE ENGINE BENCHMARK")
    print("=" * 78)
    print(f"purpose:          {args.purpose}")
    print(f"profile:          {args.profile}")
    print(f"providers:        {', '.join(providers)}")
    print(f"samples/provider: {samples}")
    print(f"MARY_CORE_URL:    {'CONFIGURED' if base_url else 'MISSING'}")
    print(f"MARY_CORE_TOKEN:  {'CONFIGURED' if token else 'MISSING'}")
    if not base_url or not token:
        return 2

    client = MaryClient(
        base_url,
        token=token,
        device_id="core-engine-benchmark",
        surface="diagnostic",
        timeout=260.0,
    )
    try:
        health = client.health()
    except Exception as exc:
        print(f"Core health:       FAIL · {type(exc).__name__}")
        return 3
    print(f"Core health:       {'PASS' if health.get('ok') else 'FAIL'}")

    records: dict[str, list[dict[str, object]]] = {name: [] for name in providers}

    for provider in providers:
        print()
        print(f"[{provider}]")
        for index in range(samples):
            request_started = time.perf_counter()
            try:
                result = client.runtime_action(
                    "llm.probe",
                    {
                        "provider": provider,
                        "purpose": args.purpose,
                        "profile": args.profile,
                    },
                )
            except MaryProtocolError as exc:
                client_ms = (time.perf_counter() - request_started) * 1000.0
                print(f"  {index + 1:>2} ERROR client={client_ms:7.1f} ms  {type(exc).__name__}")
                continue
            except Exception as exc:
                client_ms = (time.perf_counter() - request_started) * 1000.0
                print(f"  {index + 1:>2} ERROR client={client_ms:7.1f} ms  {type(exc).__name__}")
                continue

            client_ms = (time.perf_counter() - request_started) * 1000.0
            record = dict(result or {})
            record["client_ms"] = round(client_ms, 2)
            records[provider].append(record)

            status = str(record.get("status") or "unknown")
            model = str(record.get("model") or "-")[:28]
            generation_ms = record.get("generation_ms")
            usage = dict(record.get("usage") or {})
            total_tokens = usage.get("total_tokens", "-")
            print(
                f"  {index + 1:>2} {status:<16} model={model:<28} "
                f"core={_fmt(generation_ms)} ms  client={client_ms:8.1f} ms  tokens={total_tokens}"
            )
            content = " ".join(str(record.get("content") or "").split())
            if content:
                print(f"     → {content[:220]}")
            issue = record.get("output_quality")
            if issue:
                print(f"     output_quality: {issue}")

    print()
    print("SUMMARY")
    print("-" * 78)
    for provider in providers:
        good = [
            item for item in records[provider]
            if item.get("status") == "ok" and isinstance(item.get("generation_ms"), (int, float))
        ]
        if not good:
            statuses = [str(item.get("status") or "unknown") for item in records[provider]]
            print(f"{provider:<12} no successful samples ({', '.join(statuses) or 'no result'})")
            continue
        core_values = [float(item["generation_ms"]) for item in good]
        client_values = [float(item["client_ms"]) for item in good]
        models = list(dict.fromkeys(str(item.get("model") or "-") for item in good))
        print(
            f"{provider:<12} core median={statistics.median(core_values):8.1f} ms  "
            f"client median={statistics.median(client_values):8.1f} ms  "
            f"success={len(good)}/{samples}  model={'; '.join(models)}"
        )

    print()
    print("Core probe bypasses MaryApplication: no canonical turn/history/growth state is created.")
    print("Paid OpenAI is not accepted by this diagnostic. Secrets printed: no")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
