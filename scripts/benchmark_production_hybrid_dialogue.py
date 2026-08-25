"""Isolated production-path benchmark for MaryV2 hybrid dialogue.

The benchmark enters through :class:`MaryApplication` and exercises Mary's
real CharacterMind/cognition decision path.  Its only language provider is a
deterministic, counting in-process provider named ``benchmark``.  No dotenv,
live Mary data, external provider, Ollama model, or Qwen shadow is used.

Mary imports are intentionally lazy.  The isolated environment must be in
place before ``mary.core.config`` can resolve either its data or dotenv paths.
"""
from __future__ import annotations

import argparse
from collections import Counter
from contextlib import contextmanager
from dataclasses import dataclass
from datetime import datetime, timezone
import json
import math
import os
from pathlib import Path
import re
import statistics
import sys
import tempfile
from time import perf_counter
from typing import Any, Iterator, Mapping, Sequence


SCHEMA_VERSION = 1
BENCHMARK_PROVIDER = "benchmark"
BENCHMARK_MODEL = "production-benchmark-in-process"
DEFAULT_RUNS = 3
MAX_RUNS = 10
MAX_OUTPUT_CHARACTERS = 600
ISOLATION_PREFIX = "maryv2-production-hybrid-"

REQUIRED_CATEGORIES = (
    "greeting",
    "acknowledgement",
    "creator_fact",
    "mary_preference",
    "shared_history",
    "disagreement",
    "uncertainty",
    "pronoun_sensitive_relation",
    "capability_truth",
    "runtime_state",
    "casual_banter",
    "open_ended_conversation_classification",
    "thinking_required_classification",
)

_LOCAL_CLASSES = {"precision_local", "social_low_risk"}
_MODEL_ENGINES = {"conversation_generation", "task_generation"}
ROUTE_CHARACTER_MIND_LOCAL = "character_mind_local"
ROUTE_DETERMINISTIC_SYSTEM = "deterministic_system"
ROUTE_PROVIDER = "provider"
_ENV_OVERRIDES = {
    "MARY_LLM_PROVIDER": BENCHMARK_PROVIDER,
    "MARY_LLM_MODEL": BENCHMARK_MODEL,
    "MARY_LLM_FALLBACKS": "",
    "MARY_LLM_ROUTING_STRATEGY": "configured",
    "MARY_LLM_FREE_ORDER": BENCHMARK_PROVIDER,
    "MARY_LLM_CONVERSATION_ORDER": BENCHMARK_PROVIDER,
    "MARY_LLM_EXPERT_PROVIDER": BENCHMARK_PROVIDER,
    "MARY_LOCAL_MIND_ENABLED": "true",
    "MARY_LOCAL_DIALOGUE_ENABLED": "true",
    "MARY_RESERVOIR_STORAGE": "memory",
    "MARY_QWEN_SHADOW_ENABLED": "0",
    "MARY_LOCAL_MIND_SHADOW_ENABLED": "0",
    "MARY_HYBRID_QWEN_SHADOW_ENABLED": "0",
    "MARY_AUTONOMOUS": "false",
    "PYTHONDONTWRITEBYTECODE": "1",
}
_ENV_CLEARED = (
    "OPENAI_API_KEY",
    "GROQ_API_KEY",
    "GEMINI_API_KEY",
    "GOOGLE_API_KEY",
    "OPENROUTER_API_KEY",
    "OLLAMA_HOST",
    "OLLAMA_BASE_URL",
)


@dataclass(frozen=True, slots=True)
class ProductionBenchmarkCase:
    """One fixed synthetic turn and its expected production classification."""

    case_id: str
    category: str
    input_text: str
    expected_route: str
    expected_class: str | None
    expected_act: str | None

    def __post_init__(self) -> None:
        if self.category not in REQUIRED_CATEGORIES:
            raise ValueError(f"Unsupported production benchmark category: {self.category}")
        if self.expected_route not in {
            ROUTE_CHARACTER_MIND_LOCAL,
            ROUTE_DETERMINISTIC_SYSTEM,
            ROUTE_PROVIDER,
        }:
            raise ValueError(f"Unsupported execution route: {self.expected_route}")
        if self.expected_class is not None and self.expected_class not in {
            "precision_local",
            "social_low_risk",
            "open_conversation",
            "thinking_required",
        }:
            raise ValueError(f"Unsupported response class: {self.expected_class}")
        if self.expected_route == ROUTE_CHARACTER_MIND_LOCAL:
            if self.expected_class not in _LOCAL_CLASSES or not self.expected_act:
                raise ValueError("CharacterMind-local cases require a local class and act")
        elif self.expected_route == ROUTE_DETERMINISTIC_SYSTEM:
            if self.expected_class is not None or self.expected_act is not None:
                raise ValueError("system handlers bypass response-risk class and dialogue-act projection")
        elif self.expected_class is None or not self.expected_act:
            raise ValueError("provider cases require the CharacterMind escalation class and act")

    @property
    def expected_local(self) -> bool:
        """Compatibility projection; deterministic-system is intentionally separate."""

        return self.expected_route == ROUTE_CHARACTER_MIND_LOCAL


def production_benchmark_cases() -> tuple[ProductionBenchmarkCase, ...]:
    """Return the required fixed 13-category production matrix.

    The six authority-shaped but unsupported turns are intentionally literal.
    They must fail closed through CharacterMind instead of being disguised as
    locally represented semantic facts.
    """

    cases = (
        ProductionBenchmarkCase(
            "greeting",
            "greeting",
            "Hey Mary.",
            ROUTE_CHARACTER_MIND_LOCAL,
            "social_low_risk",
            "greet",
        ),
        ProductionBenchmarkCase(
            "acknowledgement",
            "acknowledgement",
            "Okay.",
            ROUTE_CHARACTER_MIND_LOCAL,
            "social_low_risk",
            "acknowledge",
        ),
        ProductionBenchmarkCase(
            "creator-fact",
            "creator_fact",
            "What's my timezone?",
            ROUTE_CHARACTER_MIND_LOCAL,
            "precision_local",
            "known_fact",
        ),
        ProductionBenchmarkCase(
            "mary-preference",
            "mary_preference",
            "Do you like blue neon?",
            ROUTE_CHARACTER_MIND_LOCAL,
            "precision_local",
            "known_preference",
        ),
        ProductionBenchmarkCase(
            "shared-history",
            "shared_history",
            "What have we worked on together?",
            ROUTE_DETERMINISTIC_SYSTEM,
            None,
            None,
        ),
        ProductionBenchmarkCase(
            "disagreement",
            "disagreement",
            "I disagree with the default approach.",
            ROUTE_PROVIDER,
            "thinking_required",
            "escalate",
        ),
        ProductionBenchmarkCase(
            "uncertainty",
            "uncertainty",
            "Do you know whether this choice is final?",
            ROUTE_PROVIDER,
            "thinking_required",
            "escalate",
        ),
        ProductionBenchmarkCase(
            "pronoun-sensitive-relation",
            "pronoun_sensitive_relation",
            "You told me that I sent the draft, but who actually sent it?",
            ROUTE_PROVIDER,
            "thinking_required",
            "escalate",
        ),
        ProductionBenchmarkCase(
            "capability-truth",
            "capability_truth",
            "What models can you use right now?",
            ROUTE_DETERMINISTIC_SYSTEM,
            None,
            None,
        ),
        ProductionBenchmarkCase(
            "runtime-state",
            "runtime_state",
            "What generated your last response?",
            ROUTE_DETERMINISTIC_SYSTEM,
            None,
            None,
        ),
        ProductionBenchmarkCase(
            "casual-banter",
            "casual_banter",
            "Wild.",
            ROUTE_CHARACTER_MIND_LOCAL,
            "social_low_risk",
            "react",
        ),
        ProductionBenchmarkCase(
            "open-conversation",
            "open_ended_conversation_classification",
            "Do constraints make conversation feel more natural or less alive?",
            ROUTE_PROVIDER,
            "open_conversation",
            "escalate",
        ),
        ProductionBenchmarkCase(
            "thinking-required",
            "thinking_required_classification",
            "Compare memory architecture tradeoffs in detail.",
            ROUTE_PROVIDER,
            "thinking_required",
            "escalate",
        ),
    )
    if len(cases) != len(REQUIRED_CATEGORIES):
        raise AssertionError("production benchmark matrix must contain exactly 13 cases")
    if tuple(case.category for case in cases) != REQUIRED_CATEGORIES:
        raise AssertionError("production benchmark categories changed or were reordered")
    return cases


# A readable compatibility name for focused tests and report tooling.
fixed_production_cases = production_benchmark_cases


class CountingBenchmarkProvider:
    """Deterministic in-process provider used only for benchmark escalation."""

    def __init__(self) -> None:
        self.generate_calls = 0
        self.availability_checks = 0
        self.call_records: list[dict[str, Any]] = []

    def provider_name(self) -> str:
        return BENCHMARK_PROVIDER

    def model_name(self) -> str:
        return BENCHMARK_MODEL

    def is_available(self) -> bool:
        self.availability_checks += 1
        return True

    def generate(
        self,
        messages: Sequence[Any],
        temperature: float = 0.7,
        max_tokens: int = 2048,
    ) -> Any:
        """Return bounded synthetic prose without touching a model or network."""

        self.generate_calls += 1
        combined = "\n".join(
            str(getattr(message, "content", "") or "")
            for message in messages
        )
        current_input = _extract_current_input(combined)
        self.call_records.append({
            "ordinal": self.generate_calls,
            "message_count": min(16, len(tuple(messages))),
            "temperature": _finite_float(temperature),
            "max_tokens": max(0, min(4096, int(max_tokens))),
            "input": _bounded_text(current_input, limit=180),
            "in_process": True,
        })

        lowered = current_input.casefold()
        if "response editor" in combined.casefold():
            content = "I should keep the answer grounded and avoid claiming details that aren't represented."
        elif "fixed that bug" in lowered:
            content = "I don't have represented evidence showing who changed that cache."
        elif "disagree" in lowered:
            content = "I disagree with making the default rigid; the context should decide."
        elif "choice is final" in lowered:
            content = "I don't know whether that choice is final from the represented state."
        elif "sent the draft" in lowered:
            content = "That wording is ambiguous, so I can't safely say who sent the draft."
        elif "camera" in lowered:
            content = "I can't verify camera access or permission from the represented runtime evidence."
        elif "runtime latency" in lowered:
            content = "The represented benchmark state does not define a live runtime latency boundary."
        elif "constraints make conversation" in lowered:
            content = "Good constraints usually make conversation feel more natural by keeping the voice grounded."
        elif "memory architecture" in lowered:
            content = (
                "A useful comparison weighs authority, retrieval latency, and failure isolation; "
                "durable truth should stay separate from rebuildable indexes."
            )
        else:
            content = "I can answer carefully from the context that is actually represented."

        # Lazy import preserves the no-dotenv-before-isolation boundary.
        from mary.llm.interface import LLMResponse

        return LLMResponse(
            content=content,
            provider=BENCHMARK_PROVIDER,
            model=BENCHMARK_MODEL,
            finish_reason="stop",
            usage={"input_tokens": 0, "output_tokens": 0, "total_tokens": 0},
        )


def _extract_current_input(prompt: str) -> str:
    match = re.search(
        r"Current user input:\s*\n(?P<input>.*?)(?:\n\n|\Z)",
        str(prompt or ""),
        flags=re.IGNORECASE | re.DOTALL,
    )
    if match is not None:
        return " ".join(match.group("input").split())
    return ""


def _bounded_text(value: Any, *, limit: int = MAX_OUTPUT_CHARACTERS) -> str:
    return " ".join(str(value or "").split()).strip()[: max(1, int(limit))]


def _finite_float(value: Any, *, default: float = 0.0) -> float:
    try:
        number = float(value)
    except (TypeError, ValueError):
        return default
    return round(number, 4) if math.isfinite(number) else default


def _optional_finite_float(value: Any) -> float | None:
    """Preserve an unmeasured timing as null rather than inventing zero."""

    if value is None:
        return None
    try:
        number = float(value)
    except (TypeError, ValueError):
        return None
    return round(number, 4) if math.isfinite(number) else None


def _mapping(value: Any) -> dict[str, Any]:
    return dict(value) if isinstance(value, Mapping) else {}


def _is_relative_to(path: Path, parent: Path) -> bool:
    try:
        path.relative_to(parent)
        return True
    except ValueError:
        return False


def validate_system_temp_isolation_root(path: str | Path) -> Path:
    """Validate a bounded benchmark root beneath the host system temp path."""

    candidate = Path(path).expanduser().resolve()
    system_temp = Path(tempfile.gettempdir()).resolve()
    if candidate == system_temp or not _is_relative_to(candidate, system_temp):
        raise ValueError("benchmark isolation root must be a child of the system temp directory")
    if not candidate.name.startswith(ISOLATION_PREFIX):
        raise ValueError(f"benchmark isolation root must start with {ISOLATION_PREFIX!r}")
    if candidate.exists() and (not candidate.is_dir() or candidate.is_symlink()):
        raise ValueError("benchmark isolation root must be a normal directory")
    return candidate


def _benchmark_environment_names() -> tuple[str, ...]:
    return tuple(sorted(
        set(_ENV_OVERRIDES) | set(_ENV_CLEARED) | {
            "MARY_DATA_DIR",
            "MARY_WORKSPACE_ROOT",
            "MARY_ENV_FILE",
            "PYTHONPYCACHEPREFIX",
        }
    ))


@contextmanager
def isolated_benchmark_environment(
    isolation_root: str | Path,
) -> Iterator[dict[str, Path]]:
    """Install and then exactly restore the benchmark's process environment."""

    root = validate_system_temp_isolation_root(isolation_root)
    if root.exists() and any(root.iterdir()):
        raise ValueError("benchmark isolation root must be fresh and empty")
    root.mkdir(parents=True, exist_ok=True)

    paths = {
        "root": root,
        "data": root / "state",
        "workspace": root / "workspace",
        "env_file": root / "no-live-config",
        "pycache": root / "pycache",
    }
    names = _benchmark_environment_names()
    previous = {name: os.environ.get(name) for name in names}
    previous_bytecode = sys.dont_write_bytecode

    try:
        for name in _ENV_CLEARED:
            os.environ.pop(name, None)
        os.environ.update(_ENV_OVERRIDES)
        os.environ["MARY_DATA_DIR"] = str(paths["data"])
        os.environ["MARY_WORKSPACE_ROOT"] = str(paths["workspace"])
        os.environ["MARY_ENV_FILE"] = str(paths["env_file"])
        os.environ["PYTHONPYCACHEPREFIX"] = str(paths["pycache"])
        sys.dont_write_bytecode = True
        yield paths
    finally:
        sys.dont_write_bytecode = previous_bytecode
        for name, value in previous.items():
            if value is None:
                os.environ.pop(name, None)
            else:
                os.environ[name] = value


def _seed_isolated_authority(mary: Any) -> None:
    """Seed synthetic authoritative fixtures inside disposable state only."""

    mary.user_model.record_profile(
        category="fact",
        key="timezone",
        value="Pacific",
        source="production_benchmark_fixture",
        confidence=1.0,
        explicitly_shared=True,
    )
    mary.preferences.set_preference(
        name="blue_neon",
        category="aesthetic",
        strength=0.9,
        polarity=0.9,
        confidence=1.0,
        source="production_benchmark_fixture",
    )
    shared_work = "We've been building the isolated production hybrid dialogue benchmark together."
    learned = mary._learn_shared_work_statement(
        shared_work,
        intent=mary.cognition.detect_intent(shared_work),
        allow_test_probe=True,
    )
    if not learned or not learned.get("recorded"):
        raise RuntimeError("isolated shared-work authority fixture was not recorded")
    mary.mind.rebuild_reservoir()


def _install_character_mind_probe(mary: Any) -> tuple[list[float], Any]:
    durations: list[float] = []
    original = mary.mind.try_respond

    def measured(*args: Any, **kwargs: Any) -> Any:
        started = perf_counter()
        try:
            return original(*args, **kwargs)
        finally:
            durations.append(round(max(0.0, (perf_counter() - started) * 1000.0), 4))

    mary.mind.try_respond = measured
    return durations, original


def _sanitized_attempts(value: Any) -> list[dict[str, Any]]:
    if not isinstance(value, Sequence) or isinstance(value, (str, bytes, bytearray)):
        return []
    output: list[dict[str, Any]] = []
    for raw in tuple(value)[:4]:
        item = _mapping(raw)
        output.append({
            "provider": _bounded_text(item.get("provider"), limit=40),
            "status": _bounded_text(item.get("status"), limit=40),
        })
    return output


def _sanitized_attempt_timings(value: Any) -> list[dict[str, Any]]:
    if not isinstance(value, Sequence) or isinstance(value, (str, bytes, bytearray)):
        return []
    output: list[dict[str, Any]] = []
    for raw in tuple(value)[:4]:
        item = _mapping(raw)
        output.append({
            "provider": _bounded_text(item.get("provider"), limit=40),
            "status": _bounded_text(item.get("status"), limit=40),
            "call_ms": _optional_finite_float(item.get("call_ms")),
            "elapsed_ms": _optional_finite_float(item.get("elapsed_ms")),
        })
    return output


def extract_cycle_metrics(
    pipeline_result: Any,
    *,
    pre_tts_pipeline_total_ms: float,
    provider_call_count: int,
    character_mind_calls: int,
    character_mind_ms: float,
) -> dict[str, Any]:
    """Extract only stable, bounded production metadata from a pipeline turn."""

    pipeline_metadata = _mapping(getattr(pipeline_result, "metadata", {}))
    cycle = _mapping(pipeline_metadata.get("pipeline_values")).get("cognitive_cycle")
    if cycle is None:
        raise ValueError("MaryApplication result did not expose cognitive_cycle")

    cycle_metadata = _mapping(getattr(cycle, "metadata", {}))
    reasoning = getattr(cycle, "reasoning", None)
    reasoning_metadata = _mapping(getattr(reasoning, "metadata", {}))
    reflection = getattr(cycle, "reflection", None)
    reflection_metadata = _mapping(getattr(reflection, "metadata", {}))
    local_mind = _mapping(cycle_metadata.get("local_mind"))
    timings = _mapping(cycle_metadata.get("timings"))

    response_class_text = _bounded_text(
        reasoning_metadata.get("response_class") or local_mind.get("response_class"),
        limit=40,
    ).lower()
    response_class = response_class_text or None
    raw_response_engine = _bounded_text(
        reasoning_metadata.get("response_engine") or local_mind.get("response_engine"),
        limit=64,
    ).lower()
    reflection_mode = _bounded_text(reflection_metadata.get("mode"), limit=64)
    llm_skipped = reasoning_metadata.get("llm_skipped") is True
    deterministic_system = bool(
        llm_skipped
        and reflection_mode == "deterministic_system_action"
    )
    if raw_response_engine == "local_composer_v2":
        execution_route = ROUTE_CHARACTER_MIND_LOCAL
    elif deterministic_system:
        execution_route = ROUTE_DETERMINISTIC_SYSTEM
    else:
        execution_route = ROUTE_PROVIDER
    if raw_response_engine:
        response_engine = raw_response_engine
    elif deterministic_system and reasoning_metadata.get("generation_purpose") == "runtime_introspection":
        response_engine = "runtime_introspection"
    elif deterministic_system:
        response_engine = "deterministic_system_action"
    else:
        response_engine = None
    provider_text = _bounded_text(reasoning_metadata.get("provider"), limit=64).lower()
    provider = provider_text or ("local/system" if deterministic_system else None)
    model_text = _bounded_text(reasoning_metadata.get("model"), limit=96)
    model = model_text or None
    escalation_reason = _bounded_text(
        reasoning_metadata.get("escalation_reason")
        or local_mind.get("escalation_reason"),
        limit=160,
    )
    plan = _mapping(local_mind.get("plan"))
    lane = _mapping(
        reasoning_metadata.get("conversation_lane")
        or local_mind.get("conversation_lane")
    )
    intent = getattr(cycle, "intent", None)
    intent_type = getattr(intent, "intent_type", None)
    intent_name = getattr(intent_type, "value", intent_type)

    timing_view = {
        "pre_tts_pipeline_total_ms": _finite_float(pre_tts_pipeline_total_ms),
        "character_mind_ms": (
            _finite_float(character_mind_ms)
            if character_mind_calls > 0
            else None
        ),
        "classification_ms": _optional_finite_float(
            local_mind.get("classification_ms", timings.get("classification_ms"))
        ),
        "local_composer_ms": _optional_finite_float(
            local_mind.get("local_composer_ms", timings.get("local_composer_ms"))
        ),
        "local_audit_ms": _optional_finite_float(
            local_mind.get("local_audit_ms", timings.get("local_audit_ms"))
        ),
        "cognition_total_ms": _optional_finite_float(timings.get("cognition_total_ms")),
    }
    shadow_enabled = bool(
        reasoning_metadata.get("shadow_enabled", local_mind.get("shadow_enabled", False))
    )
    shadow_model = reasoning_metadata.get("shadow_model", local_mind.get("shadow_model"))
    shadow_ms = reasoning_metadata.get("shadow_ms", local_mind.get("shadow_ms"))

    return {
        "pipeline_success": bool(getattr(pipeline_result, "success", False)),
        "execution_route": execution_route,
        "intent": _bounded_text(intent_name, limit=48).lower(),
        "handled_by": _bounded_text(cycle_metadata.get("handled_by"), limit=64) or None,
        "system_action": _bounded_text(cycle_metadata.get("system_action"), limit=64) or None,
        "llm_skipped": llm_skipped,
        "output": _bounded_text(getattr(cycle, "final_response", "")),
        "provider": provider,
        "model": model,
        "provider_call_count": max(0, int(provider_call_count)),
        "provider_attempts": _sanitized_attempts(reasoning_metadata.get("provider_attempts")),
        "provider_attempt_timings": _sanitized_attempt_timings(
            reasoning_metadata.get("provider_attempt_timings")
        ),
        "response_class": response_class,
        "response_classification": {
            "value": response_class,
            "source": (
                "character_mind_response_risk"
                if local_mind
                else "bypassed_by_authoritative_system_handler"
                if deterministic_system
                else "unavailable"
            ),
        },
        "response_engine": response_engine,
        "selected_response_engine": response_engine,
        "escalation_reason": escalation_reason or None,
        "character_mind": {
            "calls": max(0, int(character_mind_calls)),
            "handled": response_engine == "local_composer_v2",
            "decision": (
                "not_reached"
                if character_mind_calls == 0
                else "handled"
                if response_engine == "local_composer_v2"
                else "escalated"
            ),
            "plan": {
                key: plan.get(key)
                for key in ("act", "local", "target_length")
                if key in plan
            },
            "conversation_lane": {
                key: lane.get(key)
                for key in ("lane", "latency_target_ms", "allow_model_revision")
                if key in lane
            },
        },
        "reflection_mode": reflection_mode,
        "shadow_enabled": shadow_enabled,
        "shadow_model": _bounded_text(shadow_model, limit=96) or None,
        "shadow_ms": None if shadow_ms is None else _finite_float(shadow_ms),
        "timings": timing_view,
        **timing_view,
    }


def _sample_passes(case: ProductionBenchmarkCase, sample: Mapping[str, Any]) -> tuple[bool, list[str]]:
    failures: list[str] = []
    if sample.get("pipeline_success") is not True:
        failures.append("pipeline did not complete")
    if sample.get("response_class") != case.expected_class:
        failures.append(
            f"class {sample.get('response_class')!r} != {case.expected_class!r}"
        )
    if sample.get("shadow_enabled") is not False or sample.get("shadow_model") is not None:
        failures.append("Qwen/model shadow was not disabled")

    calls = int(sample.get("provider_call_count", 0) or 0)
    actual_route = sample.get("execution_route")
    if actual_route != case.expected_route:
        failures.append(f"route {actual_route!r} != {case.expected_route!r}")
    plan = _mapping(_mapping(sample.get("character_mind")).get("plan"))
    if case.expected_act is not None and plan.get("act") != case.expected_act:
        failures.append(f"act {plan.get('act')!r} != {case.expected_act!r}")

    if case.expected_route == ROUTE_CHARACTER_MIND_LOCAL:
        if calls != 0:
            failures.append(f"local response made {calls} provider call(s)")
        if sample.get("provider") != "local/mind":
            failures.append(f"local response selected provider {sample.get('provider')!r}")
        if sample.get("response_engine") != "local_composer_v2":
            failures.append(f"local response selected engine {sample.get('response_engine')!r}")
        if _mapping(sample.get("character_mind")).get("calls") != 1:
            failures.append("CharacterMind-local response did not make exactly one mind decision")
    elif case.expected_route == ROUTE_DETERMINISTIC_SYSTEM:
        if calls != 0:
            failures.append(f"deterministic system response made {calls} provider call(s)")
        if sample.get("provider") != "local/system":
            failures.append(f"system response selected provider {sample.get('provider')!r}")
        if sample.get("response_engine") not in {
            "deterministic_system_action",
            "runtime_introspection",
        }:
            failures.append(f"system response selected engine {sample.get('response_engine')!r}")
        if sample.get("llm_skipped") is not True:
            failures.append("deterministic system response did not report llm_skipped")
        if sample.get("reflection_mode") != "deterministic_system_action":
            failures.append("deterministic system response used a non-system reflection mode")
        if _mapping(sample.get("character_mind")).get("calls") != 0:
            failures.append("authoritative system handler should run before CharacterMind")
    else:
        if calls < 1:
            failures.append("escalated response did not call the benchmark provider")
        if sample.get("provider") != BENCHMARK_PROVIDER:
            failures.append(f"escalated response selected provider {sample.get('provider')!r}")
        if sample.get("response_engine") not in _MODEL_ENGINES:
            failures.append(f"escalated response selected engine {sample.get('response_engine')!r}")
        if _mapping(sample.get("character_mind")).get("calls") != 1:
            failures.append("provider response did not first receive one CharacterMind decision")

    attempts = sample.get("provider_attempts", [])
    if any(item.get("provider") != BENCHMARK_PROVIDER for item in attempts):
        failures.append("a non-benchmark provider was attempted")
    return not failures, failures


def _percentile(values: Sequence[Any], percentile: float) -> float | None:
    clean = sorted(
        number
        for number in (_optional_finite_float(value) for value in values)
        if number is not None
    )
    if not clean:
        return None
    if len(clean) == 1:
        return clean[0]
    rank = (len(clean) - 1) * max(0.0, min(1.0, percentile))
    lower = math.floor(rank)
    upper = math.ceil(rank)
    if lower == upper:
        return clean[lower]
    weight = rank - lower
    return round(clean[lower] * (1.0 - weight) + clean[upper] * weight, 4)


def _timing_summary(samples: Sequence[Mapping[str, Any]]) -> dict[str, dict[str, float | None]]:
    names = (
        "pre_tts_pipeline_total_ms",
        "character_mind_ms",
        "classification_ms",
        "local_composer_ms",
        "local_audit_ms",
    )
    summary: dict[str, dict[str, float | None]] = {}
    for name in names:
        values = [
            number
            for number in (_optional_finite_float(item.get(name)) for item in samples)
            if number is not None
        ]
        summary[name] = {
            "p50": round(statistics.median(values), 4) if values else None,
            "p95": _percentile(values, 0.95),
        }
    return summary


def _build_report(
    samples: list[dict[str, Any]],
    runs: int,
    provider: CountingBenchmarkProvider,
    *,
    state_evidence: Mapping[str, Any],
    blocked_provider_attempts: Sequence[str],
) -> dict[str, Any]:
    failures = [
        {"case_id": item["case_id"], "run": item["run"], "reasons": item["failures"]}
        for item in samples
        if not item["passed"]
    ]
    category_summary: dict[str, Any] = {}
    for category in REQUIRED_CATEGORIES:
        selected = [item for item in samples if item["category"] == category]
        category_summary[category] = {
            "samples": len(selected),
            "passed": sum(1 for item in selected if item["passed"]),
            "provider_calls": sum(int(item["provider_call_count"]) for item in selected),
            "response_classes": dict(sorted(Counter(
                str(item["response_class"] or "not_applicable")
                for item in selected
            ).items())),
            "response_engines": dict(sorted(Counter(
                str(item["response_engine"] or "not_applicable")
                for item in selected
            ).items())),
            "timings_ms": _timing_summary(selected),
        }
    route_summary: dict[str, Any] = {}
    for route in (
        ROUTE_CHARACTER_MIND_LOCAL,
        ROUTE_DETERMINISTIC_SYSTEM,
        ROUTE_PROVIDER,
    ):
        selected = [item for item in samples if item["execution_route"] == route]
        route_summary[route] = {
            "samples": len(selected),
            "passed": sum(1 for item in selected if item["passed"]),
            "provider_calls": sum(int(item["provider_call_count"]) for item in selected),
            "timings_ms": _timing_summary(selected),
        }

    return {
        "schema_version": SCHEMA_VERSION,
        "benchmark": "maryv2_production_hybrid_dialogue_12_12_3",
        "generated_at": datetime.now(timezone.utc).isoformat(),
        "entrypoint": "MaryApplication.run",
        "runs_per_case": runs,
        "required_categories": list(REQUIRED_CATEGORIES),
        "case_count": len(production_benchmark_cases()),
        "sample_count": len(samples),
        "provider_contract": {
            "name": BENCHMARK_PROVIDER,
            "model": BENCHMARK_MODEL,
            "implementation": "counting_in_process",
            "network_calls": 0,
            "external_provider_calls": 0,
            "blocked_external_provider_instantiations": len(blocked_provider_attempts),
            "blocked_provider_names": sorted(set(blocked_provider_attempts)),
            "generate_calls": provider.generate_calls,
            "availability_checks": provider.availability_checks,
        },
        "state_contract": dict(state_evidence),
        "shadow_contract": {
            "enabled": False,
            "model": None,
            "calls": 0,
            "qwen_promoted": False,
        },
        "summary": {
            "passed": not failures,
            "passed_samples": len(samples) - len(failures),
            "failed_samples": len(failures),
            "provider_calls": sum(int(item["provider_call_count"]) for item in samples),
            "timings_ms": _timing_summary(samples),
            "routes": route_summary,
            "categories": category_summary,
            "failures": failures[:100],
        },
        "samples": samples,
    }


def run_production_benchmark(
    *,
    runs: int = DEFAULT_RUNS,
    isolation_root: str | Path,
) -> dict[str, Any]:
    """Run the fixed matrix through an isolated real MaryApplication."""

    if isinstance(runs, bool) or not 1 <= int(runs) <= MAX_RUNS:
        raise ValueError(f"runs must be between 1 and {MAX_RUNS}")
    runs = int(runs)
    tracked_environment = {
        name: os.environ.get(name)
        for name in _benchmark_environment_names()
    }
    config_preloaded_before_isolation = "mary.core.config" in sys.modules
    report: dict[str, Any]

    with isolated_benchmark_environment(isolation_root) as paths:
        dotenv_target_absent_before_import = not paths["env_file"].exists()
        # Lazy imports are a safety property: MARY_ENV_FILE and MARY_DATA_DIR
        # are already isolated before mary.core.config can import dotenv.
        from mary.core.config import Config
        from mary.core.mary import Mary
        from mary.runtime.application import create_application

        preflight_config = Config()
        if preflight_config.paths.data.resolve() != paths["data"].resolve():
            raise RuntimeError("benchmark Config resolved a non-isolated data root")
        if paths["env_file"].exists():
            raise RuntimeError("benchmark MARY_ENV_FILE target must remain nonexistent")
        mary = Mary()
        resolved_data = mary.config.paths.data.resolve()
        if resolved_data != paths["data"].resolve():
            mary.mind.close()
            raise RuntimeError("Mary resolved a data root outside benchmark isolation")
        resolved_workspace = mary.config.paths.workspace.resolve()
        if resolved_workspace != paths["workspace"].resolve():
            mary.mind.close()
            raise RuntimeError("Mary resolved a workspace root outside benchmark isolation")

        state_evidence: dict[str, Any] = {
            "claims_scope": (
                "benchmark configuration and operations only; prior imports in an "
                "embedding process are explicitly not attested"
            ),
            "config_preloaded_before_isolation": config_preloaded_before_isolation,
            "dotenv_target_nonexistent_before_lazy_import": dotenv_target_absent_before_import,
            "dotenv_attestation": (
                "isolated nonexistent target installed before first config import"
                if not config_preloaded_before_isolation
                else "config was already imported; prior dotenv history is not attested"
            ),
            "runtime_data_root_isolated": resolved_data == paths["data"].resolve(),
            "runtime_workspace_root_isolated": resolved_workspace == paths["workspace"].resolve(),
            "repo_local_data_selected": resolved_data == (Path(__file__).resolve().parents[1] / "data").resolve(),
            "authoritative_load_options": {
                "memory": False,
                "developed_self": False,
                "preference_promotion": False,
            },
            "reservoir_storage": "memory",
            "synthetic_authority_only": True,
            "isolated_system_temp": True,
            "persistent_output_scope": "bounded runtime_reports JSON only",
        }

        provider = CountingBenchmarkProvider()
        mary.config.llm.provider = BENCHMARK_PROVIDER
        mary.config.llm.model = BENCHMARK_MODEL
        mary.config.llm.routing_strategy = "configured"
        mary.config.llm.fallback_providers = []
        mary.config.llm.expert_provider = BENCHMARK_PROVIDER
        mary.llm.register_provider(BENCHMARK_PROVIDER, provider)

        # A routing regression must fail closed instead of instantiating a live
        # provider.  The normal LLMRouter still owns the benchmark provider call.
        blocked_provider_attempts: list[str] = []

        def block_external_provider(name: str, *, purpose: str | None = None) -> Any:
            del purpose
            blocked_provider_attempts.append(_bounded_text(name, limit=40).lower())
            raise RuntimeError(f"external provider blocked by production benchmark: {name}")

        mary.llm._create_provider = block_external_provider

        app = None
        original_try_respond = None
        mind_durations: list[float] = []
        samples: list[dict[str, Any]] = []

        try:
            app = create_application(
                mary=mary,
                memory_path=paths["data"] / "memory" / "memory.json",
                developed_self_path=paths["data"] / "personality" / "developed_self.json",
                preference_promotion_path=paths["data"] / "personality" / "preference_promotion.json",
                auto_save=False,
                load_memory=False,
                load_developed_self=False,
                load_preference_promotion=False,
                name="production_hybrid_dialogue_benchmark",
            )
            _seed_isolated_authority(mary)
            mind_durations, original_try_respond = _install_character_mind_probe(mary)
            for run_number in range(1, runs + 1):
                for case in production_benchmark_cases():
                    provider_before = provider.generate_calls
                    mind_before = len(mind_durations)
                    started = perf_counter()
                    pipeline_result = app.run(
                        case.input_text,
                        turn_id=f"benchmark-{run_number}-{case.case_id}",
                        metadata={
                            "benchmark": "production_hybrid_dialogue",
                            "synthetic": True,
                        },
                    )
                    pre_tts_ms = round(max(0.0, (perf_counter() - started) * 1000.0), 4)
                    mind_slice = mind_durations[mind_before:]
                    sample = extract_cycle_metrics(
                        pipeline_result,
                        pre_tts_pipeline_total_ms=pre_tts_ms,
                        provider_call_count=provider.generate_calls - provider_before,
                        character_mind_calls=len(mind_slice),
                        character_mind_ms=sum(mind_slice),
                    )
                    sample.update({
                        "run": run_number,
                        "case_id": case.case_id,
                        "category": case.category,
                        "input": case.input_text,
                        "expected_class": case.expected_class,
                        "expected_route": case.expected_route,
                        "expected_act": case.expected_act,
                    })
                    passed, reasons = _sample_passes(case, sample)
                    sample["passed"] = passed
                    sample["failures"] = reasons
                    samples.append(sample)
        finally:
            if original_try_respond is not None:
                mary.mind.try_respond = original_try_respond
            if app is not None:
                app.close()
            else:
                mary.mind.close()

        state_evidence["dotenv_target_remained_nonexistent"] = not paths["env_file"].exists()
        report = _build_report(
            samples,
            runs,
            provider,
            state_evidence=state_evidence,
            blocked_provider_attempts=blocked_provider_attempts,
        )

    environment_restored = all(
        os.environ.get(name) == value
        for name, value in tracked_environment.items()
    )
    report["state_contract"]["environment_restored"] = environment_restored
    if not environment_restored:
        raise RuntimeError("benchmark environment was not restored exactly")
    return report


def runtime_reports_root() -> Path:
    return Path(__file__).resolve().parents[1] / "runtime_reports"


def _resolve_report_path(path: str | Path, report_root: Path) -> Path:
    raw = Path(path).expanduser()
    if raw.is_absolute():
        target = raw.resolve()
    else:
        parts = raw.parts
        if parts and parts[0].casefold() == report_root.name.casefold():
            raw = Path(*parts[1:])
        target = (report_root / raw).resolve()
    if target == report_root or not _is_relative_to(target, report_root):
        raise ValueError("benchmark report must stay beneath runtime_reports")
    if target.suffix.casefold() != ".json":
        raise ValueError("benchmark report must use a .json suffix")
    return target


def write_report_no_clobber(
    report: Mapping[str, Any],
    path: str | Path,
    *,
    report_root: str | Path | None = None,
) -> Path:
    """Write one bounded JSON report under runtime_reports, never replacing it."""

    root = Path(report_root or runtime_reports_root()).expanduser().resolve()
    target = _resolve_report_path(path, root)
    target.parent.mkdir(parents=True, exist_ok=True)
    serialized = json.dumps(dict(report), indent=2, ensure_ascii=False, sort_keys=True)
    # A generous hard ceiling prevents accidental state/prompt dumps from
    # turning this developer report into unbounded persistence.
    if len(serialized.encode("utf-8")) > 2_000_000:
        raise ValueError("benchmark report exceeds the 2 MB storage ceiling")

    created = False
    try:
        with target.open("x", encoding="utf-8", newline="\n") as handle:
            created = True
            handle.write(serialized)
            handle.write("\n")
            handle.flush()
            os.fsync(handle.fileno())
    except Exception:
        if created:
            try:
                target.unlink()
            except OSError:
                pass
        raise
    return target


write_benchmark_report = write_report_no_clobber


def _default_report_name() -> str:
    stamp = datetime.now(timezone.utc).strftime("%Y%m%d-%H%M%S-%fZ")
    return f"production-hybrid-dialogue-{stamp}.json"


def _parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--runs", type=int, default=DEFAULT_RUNS)
    parser.add_argument(
        "--save",
        default="",
        help="JSON filename/path beneath runtime_reports (existing files are refused)",
    )
    parser.add_argument(
        "--isolation-root",
        default="",
        help=argparse.SUPPRESS,
    )
    return parser


def main(argv: Sequence[str] | None = None) -> int:
    args = _parser().parse_args(argv)
    if not 1 <= args.runs <= MAX_RUNS:
        raise SystemExit(f"--runs must be between 1 and {MAX_RUNS}")

    owned_temp: tempfile.TemporaryDirectory[str] | None = None
    if args.isolation_root:
        isolation_root = validate_system_temp_isolation_root(args.isolation_root)
    else:
        owned_temp = tempfile.TemporaryDirectory(prefix=ISOLATION_PREFIX)
        isolation_root = Path(owned_temp.name)

    try:
        report = run_production_benchmark(runs=args.runs, isolation_root=isolation_root)
        report_path = write_report_no_clobber(report, args.save or _default_report_name())
    finally:
        if owned_temp is not None:
            owned_temp.cleanup()

    summary = report["summary"]
    print(
        "Production hybrid dialogue: "
        f"{summary['passed_samples']}/{report['sample_count']} samples passed; "
        f"{summary['provider_calls']} in-process provider call(s)."
    )
    print(f"Report: {report_path}")
    return 0 if summary["passed"] else 1


if __name__ == "__main__":
    raise SystemExit(main())
