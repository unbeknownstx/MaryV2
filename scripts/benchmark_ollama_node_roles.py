"""Benchmark Mary Core -> Windows capability node -> Ollama roles.

This is a transport/provider diagnostic only. It does not create Mary turns,
mutate canonical state, or call localhost directly. Core requests bounded model
roles and the connected device owns concrete model selection.
"""
from __future__ import annotations

import argparse
import os
from dataclasses import dataclass
from statistics import median
from time import monotonic, sleep
from typing import Any

from dotenv import load_dotenv

from mary.protocol.client import MaryClient, MaryProtocolError

ROLES = ("fast", "conversation", "general", "utility")
TERMINAL = {"completed", "rejected", "failed", "expired"}


@dataclass
class Sample:
    role: str
    index: int
    dispatch_ms: float
    claim_ms: float | None
    total_ms: float
    model: str
    status: str
    content: str

    @property
    def execution_ms(self) -> float | None:
        if self.claim_ms is None:
            return None
        return max(0.0, self.total_ms - self.claim_ms)


def parser() -> argparse.ArgumentParser:
    p = argparse.ArgumentParser(description=__doc__)
    p.add_argument("--roles", nargs="+", choices=ROLES, default=["fast", "general"])
    p.add_argument("--samples", type=int, default=3)
    p.add_argument("--timeout", type=float, default=210.0)
    p.add_argument("--poll", type=float, default=0.1)
    return p


def _run_sample(client: MaryClient, role: str, index: int, timeout: float, poll: float) -> Sample:
    started = monotonic()
    dispatched = client.dispatch_capability_task(
        "llm.ollama",
        f"Benchmark Mary Core to Windows Ollama role {role} sample {index}.",
        {
            "messages": [
                {"role": "system", "content": "MaryV2 infrastructure benchmark. Follow the output instruction exactly."},
                {"role": "user", "content": "Reply with exactly: MARY BENCH OK"},
            ],
            "role": role,
            "temperature": 0.0,
            "max_tokens": 24,
        },
    )
    dispatch_ms = (monotonic() - started) * 1000.0
    task = dict(dispatched.get("task") or {})
    task_id = str(task.get("task_id") or "").strip()
    if not task_id:
        raise RuntimeError("Core returned no task id.")

    deadline = monotonic() + max(10.0, min(240.0, timeout))
    claim_ms: float | None = None
    while monotonic() < deadline:
        current = client.capability_task_status(task_id)
        task = dict(current.get("task") or {})
        status = str(task.get("status") or "").strip().lower()
        elapsed_ms = (monotonic() - started) * 1000.0
        if status in {"claimed", "completed"} and claim_ms is None:
            claim_ms = elapsed_ms
        if status in TERMINAL:
            result: dict[str, Any] = dict(task.get("result") or {})
            return Sample(
                role=role,
                index=index,
                dispatch_ms=dispatch_ms,
                claim_ms=claim_ms,
                total_ms=elapsed_ms,
                model=str(result.get("model") or "unknown"),
                status=status,
                content=str(result.get("content") or "").strip(),
            )
        sleep(max(0.05, min(0.5, poll)))
    raise TimeoutError(f"Timed out waiting for role {role} sample {index}.")


def _fmt_ms(value: float | None) -> str:
    return "—" if value is None else f"{value:.1f}"


def main() -> int:
    args = parser().parse_args()
    load_dotenv()
    core_url = str(os.getenv("MARY_CORE_URL", "")).strip().rstrip("/")
    token = str(os.getenv("MARY_CORE_TOKEN", "")).strip()

    print("MARYV2 CAPABILITY-NODE OLLAMA ROLE BENCHMARK")
    print("=" * 72)
    print(f"roles:            {', '.join(args.roles)}")
    print(f"samples/role:     {max(1, args.samples)}")
    print(f"MARY_CORE_URL:    {'CONFIGURED' if core_url else 'NOT CONFIGURED'}")
    print(f"MARY_CORE_TOKEN:  {'CONFIGURED' if token else 'NOT CONFIGURED'}")
    if not core_url or not token:
        print("result:           FAIL · Core URL/token is not configured")
        return 2

    client = MaryClient(
        core_url,
        token=token,
        device_id="windows-ollama-role-benchmark",
        surface="diagnostic",
        timeout=8.0,
    )
    try:
        route = client.route_capability("llm.ollama")
    except (MaryProtocolError, OSError, ValueError) as exc:
        print(f"route:            FAIL · {type(exc).__name__}: {exc}")
        return 3
    if not bool(route.get("available")):
        print("route:            FAIL · no connected llm.ollama capability node")
        return 4

    print(f"selected node:    {route.get('selected_node_id') or 'connected node'}")
    all_samples: list[Sample] = []
    try:
        for role in args.roles:
            print()
            print(f"[{role}]")
            for index in range(1, max(1, args.samples) + 1):
                sample = _run_sample(client, role, index, args.timeout, args.poll)
                all_samples.append(sample)
                marker = "first" if index == 1 else "warm"
                print(
                    f"  {index:>2} {marker:<5}  model={sample.model:<24} "
                    f"dispatch={sample.dispatch_ms:7.1f}  claim={_fmt_ms(sample.claim_ms):>7}  "
                    f"exec≈{_fmt_ms(sample.execution_ms):>7}  total={sample.total_ms:8.1f} ms  "
                    f"{sample.status}"
                )
                if sample.status != "completed" or not sample.content:
                    print("result:           FAIL · benchmark task did not complete with content")
                    return 5
    except (MaryProtocolError, OSError, ValueError, RuntimeError, TimeoutError) as exc:
        print(f"result:           FAIL · {type(exc).__name__}: {exc}")
        return 6

    print()
    print("SUMMARY")
    print("-" * 72)
    for role in args.roles:
        rows = [s for s in all_samples if s.role == role and s.status == "completed"]
        if not rows:
            continue
        warm = rows[1:] if len(rows) > 1 else rows
        models = sorted({s.model for s in rows})
        warm_exec = [s.execution_ms for s in warm if s.execution_ms is not None]
        print(f"{role:14} model: {', '.join(models)}")
        print(f"{'':14} first total: {rows[0].total_ms:.1f} ms")
        print(f"{'':14} warm median total: {median(s.total_ms for s in warm):.1f} ms")
        if warm_exec:
            print(f"{'':14} warm median execution≈: {median(warm_exec):.1f} ms")
        print(f"{'':14} warm median claim: {median(s.claim_ms for s in warm if s.claim_ms is not None):.1f} ms")
    print()
    print("Note: first sample is diagnostic/cold-ish; use warm medians for routing decisions.")
    print("No canonical Mary state was changed. Secrets printed: no")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
