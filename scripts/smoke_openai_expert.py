"""One intentionally enabled paid OpenAI expert smoke test.

This script makes exactly one small OpenAI consultation and never sends Mary's
persistent memory or creator profile. It only sends the temporary task text
created below.
"""

from __future__ import annotations

import os

from dotenv import load_dotenv

from mary.core.config import Config
from mary.llm.router import LLMRouter
from mary.orchestration import ExpertConsultant, TaskWorkspaceManager


def main() -> int:
    load_dotenv()

    if os.getenv("MARY_RUN_OPENAI_TESTS", "").strip().lower() not in {
        "1", "true", "yes", "on"
    }:
        print("OPENAI LIVE SMOKE NOT RUN")
        print("Set MARY_RUN_OPENAI_TESTS=1 intentionally to permit one paid call.")
        return 2

    if not os.getenv("OPENAI_API_KEY", "").strip():
        print("OPENAI LIVE SMOKE NOT RUN: OPENAI_API_KEY is not configured.")
        return 2

    config = Config.from_environment()
    router = LLMRouter(config)
    workspace = TaskWorkspaceManager()
    consultant = ExpertConsultant(router, workspace)

    task = workspace.create_task(
        "Verify MaryV2's paid expert consultation bridge with minimal context.",
        metadata={
            "allow_paid": True,
            "needs_expert": True,
            "source": "openai_live_smoke",
        },
    )
    result = consultant.consult(
        task.task_id,
        (
            "In one concise sentence, explain why an AI system should test "
            "assumptions instead of trusting a single model response."
        ),
        max_tokens=160,
    )

    print("MARYV2 OPENAI EXPERT LIVE SMOKE")
    print("=" * 72)
    print(f"provider:      {result.provider}")
    print(f"model:         {result.model}")
    print(f"finish_reason: {result.finish_reason}")
    print(f"usage:         {result.usage}")
    print(
        "attempts:      "
        + ", ".join(
            f"{item.get('provider')}={item.get('status')}"
            for item in result.provider_attempts
        )
    )
    print(f"response:      {result.content}")
    print(f"consultations: {len(task.consultations)}")
    print(f"evidence:      {len(task.evidence)}")

    assert result.provider == "openai"
    assert result.content.strip()
    assert task.consultations[-1].source == "openai"
    assert task.evidence[-1].provenance == "openai"

    print("=" * 72)
    print("OPENAI EXPERT LIVE SMOKE PASS")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())

