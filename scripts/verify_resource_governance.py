"""Verify MaryV2 bounded resource and paid-call governance."""
from __future__ import annotations

from mary.runtime.application import create_application


def check(label: str, condition: bool) -> None:
    if not condition:
        raise AssertionError(label)
    print(f"PASS  {label}")


def main() -> int:
    print("=" * 72)
    print("MARYV2 RESOURCE GOVERNANCE")
    print("=" * 72)
    app = create_application()
    mary = app.mary
    limits = mary.config.governance
    governor = mary.llm.resource_governor

    check("active context has a hard turn ceiling", limits.context_turns > 0)
    check("episodic and semantic memory have hard capacities", limits.episodic_capacity > 0 and limits.semantic_capacity > 0)
    check("task workspace has hard per-task and total capacities", limits.task_capacity > 0 and limits.task_evidence_capacity > 0)
    check("provider attempts per generation are capped", governor.provider_order(["a", "b", "c", "d", "e"]).__len__() <= limits.provider_attempts_per_generation)
    check("paid calls are capped per task", limits.paid_calls_per_task >= 1 and governor.paid_remaining("probe") == limits.paid_calls_per_task)
    status = governor.status()
    check("resource status contains counters but no prompt/message bodies", "messages" not in status and "content" not in repr(status.get("last_generation", {})).lower())
    try:
        print("=" * 72)
        print("RESOURCE GOVERNANCE VERIFIED")
        return 0
    finally:
        app.close()


if __name__ == "__main__":
    raise SystemExit(main())
