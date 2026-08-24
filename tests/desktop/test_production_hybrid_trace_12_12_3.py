from __future__ import annotations

import json
from pathlib import Path
from types import SimpleNamespace
from typing import Any

from mary.desktop.turn_trace import build_turn_trace


ROOT = Path(__file__).resolve().parents[2]


def _trace(
    *,
    reasoning_metadata: dict[str, Any],
    cycle_metadata: dict[str, Any],
) -> dict[str, Any]:
    cycle = SimpleNamespace(
        reasoning=SimpleNamespace(metadata=reasoning_metadata),
        reflection=SimpleNamespace(metadata={"mode": "local_mind_no_model"}),
        metadata=cycle_metadata,
    )
    result = SimpleNamespace(
        turn_id="turn_hybrid",
        metadata={"pipeline_values": {"cognitive_cycle": cycle}},
    )
    return build_turn_trace(
        result,
        pipeline_ms=9.5,
        avatar_ms=0.5,
        voice_payload={"enabled": False, "status": "disabled", "timings": {}},
        worker_total_ms=10.5,
    )


def test_local_composer_trace_reports_zero_provider_route_and_local_timings():
    local_mind = {
        "response_class": "precision_local",
        "response_engine": "local_composer_v2",
        "classification_ms": 0.21,
        "local_composer_ms": 0.72,
        "local_audit_ms": 0.18,
        "shadow_enabled": False,
        "conversation_lane": {"lane": "conversation"},
        "plan": {
            "act": "known_fact",
            "local": True,
            "target_length": "brief",
            "slots": {"fact": "must stay internal"},
        },
    }
    trace = _trace(
        reasoning_metadata={
            "provider": "local/mind",
            "model": "local-composer-v2",
            "generation_purpose": "local_dialogue",
            "response_class": "precision_local",
            "response_engine": "local_composer_v2",
            "conversation_lane": {"lane": "conversation"},
            "provider_attempts": [],
            "provider_attempt_timings": [],
        },
        cycle_metadata={
            "local_mind": local_mind,
            "timings": {
                "classification_ms": 0.21,
                "local_composer_ms": 0.72,
                "local_audit_ms": 0.18,
            },
        },
    )

    assert trace["provider"] == "local/mind"
    assert trace["model"] == "local-composer-v2"
    assert trace["response_class"] == "precision_local"
    assert trace["response_engine"] == "local_composer_v2"
    assert trace["local_mind"]["conversation_lane"] == {"lane": "conversation"}
    assert trace["attempts"] == []
    assert "provider_call_ms" not in trace["timings"]
    assert trace["timings"]["classification_ms"] == 0.21
    assert trace["timings"]["local_composer_ms"] == 0.72
    assert trace["timings"]["local_audit_ms"] == 0.18


def test_escalated_open_conversation_trace_keeps_provider_and_decision_metadata():
    trace = _trace(
        reasoning_metadata={
            "provider": "groq",
            "model": "fast-conversation-model",
            "generation_purpose": "conversation",
            "routing_purpose": "conversation_fast",
            "conversation_lane": {"lane": "conversation"},
            "response_class": "open_conversation",
            "response_engine": "conversation_generation",
            "escalation_reason": "open-ended language requires conversation generation",
            "provider_attempts": [{"provider": "groq", "status": "success"}],
            "provider_attempt_timings": [{"elapsed_ms": 19.2, "call_ms": 18.6}],
        },
        cycle_metadata={
            "local_mind": {
                "response_class": "open_conversation",
                "classification_ms": 0.14,
                "escalation_reason": "open-ended language requires conversation generation",
                "conversation_lane": {"lane": "conversation"},
            },
            "timings": {"classification_ms": 0.14, "reasoning_ms": 19.5},
        },
    )

    assert trace["provider"] == "groq"
    assert trace["response_class"] == "open_conversation"
    assert trace["response_engine"] == "conversation_generation"
    assert trace["escalation_reason"].startswith("open-ended")
    assert trace["attempts"] == [
        {
            "provider": "groq",
            "status": "success",
            "elapsed_ms": 19.2,
            "call_ms": 18.6,
        }
    ]
    assert trace["timings"]["provider_call_ms"] == 18.6


def test_turn_trace_redacts_local_plan_semantics_and_unknown_metadata():
    sentinels = {
        "SEMANTIC_UNIT_SENTINEL",
        "FACT_VALUE_SENTINEL",
        "SLOT_VALUE_SENTINEL",
        "CANONICAL_PLAN_SENTINEL",
        "PLAN_RATIONALE_SENTINEL",
    }
    trace = _trace(
        reasoning_metadata={
            "provider": "local/mind",
            "model": "local-composer-v2",
            "response_class": "social_low_risk",
            "response_engine": "local_composer_v2",
            "conversation_lane": {"lane": "social_instant"},
        },
        cycle_metadata={
            "local_mind": {
                "response_class": "social_low_risk",
                "response_engine": "local_composer_v2",
                "conversation_lane": {"lane": "social_instant"},
                "semantic_units": ["SEMANTIC_UNIT_SENTINEL"],
                "facts": {"creator": "FACT_VALUE_SENTINEL"},
                "values": ["FACT_VALUE_SENTINEL"],
                "canonical_plan": {"raw": "CANONICAL_PLAN_SENTINEL"},
                "plan": {
                    "act": "greet",
                    "local": True,
                    "target_length": "micro",
                    "rationale": "PLAN_RATIONALE_SENTINEL",
                    "slots": {"value": "SLOT_VALUE_SENTINEL"},
                    "semantic_units": ["SEMANTIC_UNIT_SENTINEL"],
                },
            }
        },
    )

    encoded = json.dumps(trace, sort_keys=True)
    for sentinel in sentinels:
        assert sentinel not in encoded
    assert trace["local_mind"]["plan"] == {
        "act": "greet",
        "local": True,
        "target_length": "micro",
    }
    assert set(trace["local_mind"]) <= {
        "response_class",
        "response_engine",
        "escalation_reason",
        "classification_ms",
        "local_composer_ms",
        "local_audit_ms",
        "shadow_enabled",
        "shadow_model",
        "shadow_ms",
        "elapsed_ms",
        "local_only",
        "conversation_lane",
        "plan",
    }


def test_runtime_diagnostics_labels_hybrid_route_and_local_timing_fields():
    source = (ROOT / "desktop" / "src" / "main.js").read_text(encoding="utf-8")

    for label in (
        "Response class",
        "Engine",
        "Escalation",
        "Shadow",
        "Classification",
        "Local composer",
        "Local audit",
    ):
        assert label in source
    for timing_key in (
        "classification_ms",
        "local_composer_ms",
        "local_audit_ms",
        "shadow_ms",
    ):
        assert timing_key in source
