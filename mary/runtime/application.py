"""
MaryV2 - Canonical Application Runtime

Builds the complete MaryV2 application runtime used by terminal entry points.

The application runtime connects:

    Mary
      ↓
    MaryStage
      ↓
    Pipeline

It does not replace Mary's subsystem logic. Mary remains the coordinator for
identity, memory, cognition, knowledge, learning, agency, autonomy,
conversation, expression, avatar, and audio.
"""

from __future__ import annotations

from dataclasses import dataclass
import os
from pathlib import Path
from typing import Any

from mary.core.mary import Mary
from mary.runtime.mary_stage import MaryStage
from mary.runtime.pipeline import Pipeline, PipelineResult
from mary.runtime.state import RuntimeState




# ================================================================
# INTERACTIVE TERMINAL UX
# ================================================================


_POWERSHELL_PREFIXES = (
    "test-path ",
    "get-content ",
    "set-content ",
    "add-content ",
    "remove-item ",
    "copy-item ",
    "move-item ",
    "get-childitem",
    "get-location",
    "set-location ",
    "new-item ",
    "select-string ",
    "where-object ",
    "foreach-object ",
    "resolve-path ",
    "join-path ",
    "split-path ",
    "python ",
    "py ",
    "pytest ",
    "pip ",
    "git ",
    "cd ",
)


def looks_like_terminal_command(text: str) -> bool:
    """Return True for command-shaped input meant for PowerShell/terminal.

    The interactive Mary prompt never executes these commands.  This helper is
    only a usability guard so command text is not accidentally sent to the LLM
    and described as though Mary had or lacked a capability.
    """

    value = str(text or "").strip()
    if not value:
        return False

    lowered = value.lower()

    # Natural-language questions about commands should still reach Mary.
    if lowered.startswith((
        "what ",
        "why ",
        "how ",
        "explain ",
        "tell me ",
    )):
        return False

    if lowered in {"dir", "ls", "pwd"}:
        return True

    return lowered.startswith(_POWERSHELL_PREFIXES)


def terminal_command_guidance(text: str) -> str:
    """Explain where a terminal-shaped command should be entered."""

    command = str(text or "").strip()
    return (
        "That looks like a PowerShell/terminal command, so I did not execute "
        "or send it through Mary's reasoning pipeline.\n\n"
        f"Run this at the PowerShell prompt instead:\n{command}\n\n"
        "You can use a second VS Code terminal while Mary stays open, or type "
        "`exit` here first and then run the command."
    )


def format_pending_requests(application: "MaryApplication") -> str:
    """Return a compact creator-facing list of pending approvals."""

    pending = application.mary.tools.pending_requests()
    if not pending:
        return "There are no pending tool requests."

    lines = ["Pending tool requests:"]
    for request in pending:
        lines.append(
            f"- {request.request_id}: {request.tool_name}"
        )

    if len(pending) == 1:
        lines.append("Say `approve` to approve it, or `reject` to reject it.")
    else:
        lines.append(
            "More than one request is pending. Use `approve request_...` or "
            "`reject request_...` with the exact id."
        )

    return "\n".join(lines)


def format_last_turn(result: Any) -> str:
    """Return a compact debug view of the most recent Mary turn."""

    if result is None:
        return "There is no completed Mary turn to inspect yet."

    try:
        values = dict(getattr(result, "metadata", {}).get("pipeline_values", {}) or {})
        cycle = values.get("cognitive_cycle")
    except Exception:
        cycle = None

    if cycle is None:
        return "The last pipeline result does not contain a cognitive-cycle debug record."

    intent = getattr(cycle, "intent", None)
    intent_name = (
        getattr(getattr(intent, "intent_type", None), "value", None)
        or "unknown"
    )
    reasoning = getattr(cycle, "reasoning", None)
    reflection = getattr(cycle, "reflection", None)
    reasoning_meta = dict(getattr(reasoning, "metadata", {}) or {})
    reflection_meta = dict(getattr(reflection, "metadata", {}) or {})
    usage = dict(reasoning_meta.get("usage", {}) or {})

    attempts = reasoning_meta.get("provider_attempts", []) or []
    attempt_text = ", ".join(
        f"{item.get('provider')}={item.get('status')}"
        for item in attempts
        if isinstance(item, dict)
    ) or "none"

    expert = dict(reasoning_meta.get("expert_consultation", {}) or {})
    turn_policy = dict(reasoning_meta.get("turn_policy", {}) or {})
    lines = [
        "Last Mary turn:",
        f"- intent: {intent_name}",
        f"- provider: {reasoning_meta.get('provider', 'local/system')}",
        f"- model: {reasoning_meta.get('model', 'n/a')}",
        f"- finish_reason: {reasoning_meta.get('finish_reason', 'n/a')}",
        f"- prompt_tokens: {usage.get('prompt_tokens', 'n/a')}",
        f"- completion_tokens: {usage.get('completion_tokens', 'n/a')}",
        f"- reasoning_tokens: {usage.get('reasoning_tokens', 'n/a')}",
        f"- attempts: {attempt_text}",
        f"- self_grounded: {reasoning_meta.get('self_grounded', False)}",
        f"- self_provenance_issue: {reasoning_meta.get('self_provenance_issue')}",
        f"- generation_purpose: {reasoning_meta.get('generation_purpose', 'default/task')}",
        f"- turn_policy: {turn_policy.get('category', 'legacy/default')}",
        f"- reflection_mode: {reflection_meta.get('mode', 'n/a')}",
    ]
    if expert:
        lines.extend([
            f"- expert_provider: {expert.get('provider', 'n/a')}",
            f"- expert_model: {expert.get('model', 'n/a')}",
            f"- expert_paid: {bool(expert.get('paid', True))}",
        ])
    return "\n".join(lines)


def format_live_state(application: "MaryApplication") -> str:
    """Return Mary's compact character card for terminal/UI parity."""

    from mary.runtime.live_state import format_character_card

    return format_character_card(application.mary.live_state())


def format_resource_state(application: "MaryApplication") -> str:
    """Return compact bounded-resource counters without prompt or secret data."""

    state = application.mary.live_state()
    resources = dict(state.get("resources", {}) or {})
    memory = dict(state.get("memory", {}) or {})
    capacities = dict(memory.get("capacities", {}) or {})
    lines = [
        "MARYV2 RESOURCE STATE",
        "────────────────────────────────",
        f"Provider attempts: {resources.get('provider_attempts', 0)}",
        f"Paid calls:        {resources.get('paid_calls', 0)}",
        f"Prompt tokens:     {resources.get('prompt_tokens', 0)}",
        f"Completion tokens: {resources.get('completion_tokens', 0)}",
        f"Reasoning tokens:  {resources.get('reasoning_tokens', 0)}",
        f"Episodic memory:   {memory.get('episodic', 0)} / {capacities.get('episodic', '?')}",
        f"Semantic memory:   {memory.get('semantic', 0)} / {capacities.get('semantic', '?')}",
        f"Working memory:    {memory.get('working', 0)} / {capacities.get('working', '?')}",
        "Paid expert policy: explicit task authorization",
    ]
    return "\n".join(lines)


def format_memory_status(application: "MaryApplication") -> str:
    """Show why memory did or did not change without exposing private bodies."""

    state = application.mary.memory_lifecycle_status()
    counts = dict(state.get("counts", {}) or {})
    capacities = dict(state.get("capacities", {}) or {})
    last_event = dict(state.get("last_memory_event", {}) or {})
    consolidation = dict(state.get("consolidation", {}) or {})
    shared = dict(state.get("shared_work", {}) or {})
    last_shared = dict(shared.get("last_learning", {}) or {})
    last_recall = dict(shared.get("last_recall", {}) or {})

    lines = [
        "MARYV2 MEMORY LIFECYCLE",
        "────────────────────────────────",
        f"Episodic: {counts.get('episodic', 0)} / {capacities.get('episodic', '?')}",
        f"Semantic: {counts.get('semantic', 0)} / {capacities.get('semantic', '?')}",
        f"Working:  {counts.get('working', 0)} / {capacities.get('working', '?')}",
        "",
        "Last durable memory action:",
        f"- operation: {last_event.get('operation', 'none')}",
        f"- detected: {last_event.get('detected', 'n/a')}",
        f"- stored: {last_event.get('stored', False)}",
        f"- relationship_committed: {last_event.get('relationship_committed', False)}",
        f"- reason: {last_event.get('reason', 'n/a')}",
        "",
        "Semantic consolidation:",
        f"- automatic during normal conversation: {'YES' if consolidation.get('automatic') else 'NO'}",
        f"- currently eligible candidates: {consolidation.get('eligible_candidates', 0)}",
        f"- explanation: {consolidation.get('reason', 'unknown')}",
        "",
        f"Durable shared-work events: {shared.get('durable_events', 0)}",
        f"Last shared-work detection: recorded={last_shared.get('recorded', False)} reason={last_shared.get('reason', 'n/a')}",
    ]
    if last_recall:
        lines.extend([
            f"Last shared-work recall: candidates={last_recall.get('candidate_count', 0)} selected={last_recall.get('selected_count', 0)}",
            "Recall sources: " + (", ".join(map(str, last_recall.get('sources', []))) or "none"),
        ])
    return "\n".join(lines)


def format_conversation_state(application: "MaryApplication") -> str:
    """Show Mary 13.0 intentional-conversation state."""

    state = application.mary.engagement.status()
    active = dict(state.get("active_session", {}) or {})
    last = dict(state.get("last_plan", {}) or {})
    lines = [
        "MARYV2 CONVERSATION ENGINE",
        "────────────────────────────────",
        f"Configured mode: {state.get('mode', 'adaptive')}",
        f"Active thread: {active.get('mode') or 'none'}",
        f"Turns remaining: {active.get('turns_remaining', 0)}",
        f"Last effective mode: {last.get('effective_mode', 'n/a')}",
        f"Initiative: {last.get('initiative', 'n/a')}",
        f"Reasoning depth: {last.get('reasoning_depth', 'n/a')}",
        "Natural cues such as ‘let’s talk’, ‘ask me questions’, and ‘go deeper’ can open a thread.",
    ]
    return "\n".join(lines)


def format_growth_state(application: "MaryApplication") -> str:
    """Show display-safe continuous-development counters and policy."""

    state = application.mary.growth.status()
    journal = dict(state.get("journal", {}) or {})
    candidates = list(state.get("preference_candidates", []) or [])
    milestones = list(state.get("recent_milestones", []) or [])
    lines = [
        "MARYV2 DEVELOPMENT ENGINE",
        "────────────────────────────────",
        f"Experience records: {journal.get('records', 0)}",
        f"Meaningful experiences: {journal.get('meaningful_records', 0)}",
        f"Semantic promotions this runtime: {state.get('semantic_promotions', 0)}",
        f"Developed preferences this runtime: {state.get('preference_promotions', 0)}",
        f"Development candidates: {len(candidates)}",
        f"Milestones: {len(milestones)}",
        "Policy: grounded experience may develop represented state; model dialogue alone cannot rewrite Mary.",
    ]
    return "\n".join(lines)


def format_realtime_state(application: "MaryApplication") -> str:
    """Show Mary 13.1 realtime interaction/attention coordination state."""

    state = application.mary.realtime.status()
    stats = dict(state.get("stats", {}) or {})
    attention = dict(state.get("attention", {}) or {})
    next_event = dict(attention.get("next", {}) or {})
    lines = [
        "MARYV2 REALTIME INTERACTION",
        "────────────────────────────────",
        f"Phase: {state.get('phase', 'idle')}",
        f"Anti-echo: {'ON' if state.get('anti_echo') else 'OFF'}",
        f"Turns: {stats.get('turns', 0)}",
        f"Speech starts: {stats.get('speech_starts', 0)}",
        f"Interruptions: {stats.get('interruptions', 0)}",
        f"Suppressed echo inputs: {stats.get('suppressed_echo_inputs', 0)}",
        f"Attention pending: {attention.get('pending', 0)}",
        f"Attention published/claimed/dropped: {attention.get('published', 0)}/{attention.get('claimed', 0)}/{attention.get('dropped', 0)}",
        f"Next attention source: {next_event.get('source', 'none')}",
        "Policy: attention priority coordinates realtime work; it never changes memory or identity authority.",
    ]
    return "\n".join(lines)


def format_nodes_state(application: "MaryApplication") -> str:
    """Show registered compute nodes and their bounded capabilities."""

    state = application.mary.node_registry.snapshot()
    nodes = list(state.get("nodes", []) or [])
    lines = [
        "MARYV2 COMPUTE NODES",
        "────────────────────────────────",
        f"Registered: {len(nodes)}",
    ]
    for node in nodes:
        caps = [name for name, info in dict(node.get("capabilities", {}) or {}).items() if info.get("available")]
        lines.append(
            f"- {node.get('node_id', 'unknown')}: {'ONLINE' if node.get('connected') else 'OFFLINE'} "
            f"({node.get('role', 'node')}) · {', '.join(caps[:12]) or 'no advertised capabilities'}"
        )
    lines.append("Policy: nodes provide replaceable compute/capabilities; canonical Mary state is not node-owned.")
    return "\n".join(lines)


def format_retrieval_state(application: "MaryApplication") -> str:
    """Show hybrid lexical/vector retrieval status without triggering embeddings."""

    retriever = getattr(application.mary.mind, "retrieval", None)
    state = retriever.status() if retriever is not None else {}
    vector = dict(state.get("vector_index", {}) or {})
    weights = dict(state.get("weights", {}) or {})
    lines = [
        "MARYV2 HYBRID MEMORY RETRIEVAL",
        "────────────────────────────────",
        f"Mode: {state.get('mode', 'unavailable')}",
        f"Embedding model: {state.get('embedding_model', 'n/a')}",
        f"Vector index records: {vector.get('vectors', 0)}",
        f"Vectors requested now: {'YES' if state.get('vector_requested') else 'NO'}",
        f"Last query used vectors: {'YES' if state.get('last_query_used_vectors') else 'NO'}",
        f"Weights lexical/vector: {weights.get('lexical', 'n/a')} / {weights.get('vector', 'n/a')}",
        f"Last vector error: {state.get('last_vector_error') or 'none'}",
        "Policy: vector similarity retrieves candidates only; canonical memory/provenance still decides truth.",
    ]
    return "\n".join(lines)


def format_route_state(application: "MaryApplication") -> str:
    """Show preferred policy, host availability, and effective routes truthfully."""

    mary = application.mary
    override = (
        mary.llm.session_override_status()
        if callable(getattr(mary.llm, "session_override_status", None))
        else {"provider": None, "route": None}
    )
    last = dict(getattr(mary, "_last_generation_metadata", None) or {})
    environment = mary.runtime_environment.snapshot()
    providers = dict(environment.get("providers", {}) or {})
    active = (
        "private/ollama" if override.get("route") == "private"
        else str(override.get("provider")) if override.get("provider")
        else "normal policy"
    )
    lines = [
        "MARYV2 MODEL ROUTE",
        "────────────────────────────────",
        f"Host: {environment.get('host_type', 'unknown')} / {environment.get('platform', 'unknown')}",
        "Conversation policy: " + " -> ".join(str(x) for x in environment.get("conversation_policy", [])),
        "Effective conversation: " + (" -> ".join(str(x) for x in environment.get("effective_conversation_route", [])) or "none"),
        "Task/general policy: " + " -> ".join(str(x) for x in environment.get("task_policy", [])),
        "Effective task/general: " + (" -> ".join(str(x) for x in environment.get("effective_task_route", [])) or "none"),
        f"Temporary override: {active}",
        f"Last actual provider: {last.get('provider', 'none yet')}",
        f"Last actual model: {last.get('model', 'n/a')}",
        "Providers:",
    ]
    for name, info in providers.items():
        state = "READY" if info.get("available") else "UNAVAILABLE"
        lines.append(f"- {name}: {state} / {info.get('model', 'unknown')}")
    lines.append("Paid OpenAI: explicit one-task expert authorization only")
    return "\n".join(lines)


def format_environment_state(application: "MaryApplication") -> str:
    """Display the process-local host/capability snapshot."""

    state = application.mary.runtime_environment.snapshot()
    lines = [
        "MARYV2 HOST / CAPABILITIES",
        "────────────────────────────────",
        f"Host: {state.get('host_type', 'unknown')}",
        f"Platform: {state.get('platform', 'unknown')}",
        f"Runtime mode: {state.get('runtime_mode', 'unknown')}",
        "Capabilities:",
    ]
    for name, enabled in dict(state.get("capabilities", {}) or {}).items():
        lines.append(f"- {name}: {'YES' if enabled else 'NO'}")
    return "\n".join(lines)


def format_system_contract(application: "MaryApplication") -> str:
    """Show the display-safe ownership/routing contract for this Mary process."""

    contract = application.mary.system_contract.snapshot(application.mary)
    authority = dict(contract.get("authority", {}) or {})
    lines = [
        "MARYV2 SYSTEM CONTRACT",
        "────────────────────────────────",
        f"Version: {contract.get('version', 'unknown')}",
        f"Single LLM router: {contract.get('single_llm_router', False)}",
        f"Shared emotion state: {contract.get('shared_emotion_state', False)}",
        "Conversation route: " + " -> ".join(str(x) for x in contract.get("conversation_route", [])),
        "Task/general route: " + " -> ".join(str(x) for x in contract.get("task_route", [])),
        "Paid OpenAI sticky route: disabled",
        "Background browsing: disabled",
        "",
        "Authority owners:",
    ]
    for key, owner in authority.items():
        lines.append(f"- {key}: {owner}")
    return "\n".join(lines)


def interactive_help(application: "MaryApplication") -> str:
    """Explain the difference between Mary's prompt and PowerShell."""

    workspace = application.mary.tools.workspace_root
    return (
        "MaryV2 terminal help\n\n"
        "At `You:` type requests for Mary, for example:\n"
        "  who are you?\n"
        "  remember that <something you genuinely want Mary to retain>\n"
        "  show me what's in mary/memory\n"
        "  analyze mary/memory/manager.py\n"
        "  create file test.txt with hello\n\n"
        "PowerShell commands do NOT belong at the `You:` prompt, for example:\n"
        "  python -m pytest tests -q\n"
        "  Test-Path test.txt\n"
        "  Get-Content test.txt\n"
        "  Remove-Item test.txt\n\n"
        "Run those in a VS Code PowerShell terminal instead. You can open a "
        "second terminal while Mary stays running.\n\n"
        "Inside Mary, `/pending` shows pending approvals. If exactly one request "
        "is pending, simply type `approve` or `reject`. `/last` shows compact "
        "debug metadata for Mary's most recent completed turn. `/state` shows "
        "Mary's live character state, `/resources` shows bounded usage, `/contract` shows the architecture authority map, and `/audit` "
        "runs a read-only check for test/probe residue in creator state.\n\n"
        f"Mary's bounded workspace is: {workspace}"
    )


@dataclass
class MaryApplication:
    """
    Complete application composition for one MaryV2 process.
    """

    mary: Mary
    state: RuntimeState
    pipeline: Pipeline
    memory_path: Path
    developed_self_path: Path
    preference_promotion_path: Path | None = None

    def run(
        self,
        input_text: str,
        *,
        turn_id: str | None = None,
        metadata: dict[str, Any] | None = None,
    ) -> PipelineResult:
        """Process one input through the canonical Mary pipeline.

        13.1 wraps the existing pipeline with ephemeral realtime lifecycle
        bookkeeping. This does not change cognition or persistence; it simply
        gives every client one interruption/attention state model.
        """

        meta = dict(metadata or {})
        surface = str(meta.get("surface") or "runtime")
        transport = str(meta.get("transport") or "direct")
        voice = bool(meta.get("voice_input", False))
        interaction = None
        try:
            interaction = self.mary.realtime.begin_turn(
                input_text,
                surface=surface,
                transport=transport,
                voice=voice,
            )
        except Exception:
            interaction = None

        try:
            result = self.pipeline.run(
                input_text,
                turn_id=turn_id,
                metadata=meta,
            )
        except Exception as exc:
            try:
                self.mary.realtime.fail_turn(f"{type(exc).__name__}: {exc}")
            except Exception:
                pass
            raise

        try:
            response_text = str(getattr(result, "output", "") or "")
            if bool(getattr(result, "success", False)):
                self.mary.realtime.mark_responding(response_text=response_text)
                self.mary.realtime.finish_turn(response_text=response_text)
            else:
                self.mary.realtime.fail_turn(str(getattr(result, "error", "pipeline_failed") or "pipeline_failed"))
            result.metadata.setdefault("realtime", self.mary.realtime.status())
            if interaction is not None:
                result.metadata.setdefault("interaction_turn_id", interaction.id)
        except Exception:
            pass
        return result

    def save(self) -> bool:
        """Persist Mary's durable memory and explicitly developed self-state."""

        memory_saved = self.mary.memory.save()
        developed_saved = self.mary.save_developed_self_state()
        promotion_saved = self.mary.save_preference_promotion_state()
        engagement_saved = True
        growth_saved = True
        feedback_saved = True
        try:
            engagement_saved = bool(self.mary.engagement.save())
        except Exception:
            engagement_saved = False
        try:
            growth_saved = bool(self.mary.growth.journal.save())
        except Exception:
            growth_saved = False
        try:
            # A path may be configured even when there are no explicit ratings.
            # Avoid creating an empty private dataset solely because Mary exits.
            if self.mary.training_feedback.status().get("records", 0):
                feedback_saved = bool(self.mary.training_feedback.save())
        except Exception:
            feedback_saved = False
        return bool(
            memory_saved
            and developed_saved
            and promotion_saved
            and engagement_saved
            and growth_saved
            and feedback_saved
        )

    def close(self) -> bool:
        """Persist state needed when the application exits."""

        saved = self.save()
        try:
            # Flush any deferred *derived* reservoir refresh after canonical
            # state has been saved. This work is outside conversational latency.
            self.mary.mind.maintenance()
        except Exception:
            pass
        try:
            self.mary.mind.close()
        except Exception:
            pass
        return saved


def create_persistent_mary(
    *,
    memory_path: str | Path | None = None,
    developed_self_path: str | Path | None = None,
    preference_promotion_path: str | Path | None = None,
    auto_save: bool = True,
    load_memory: bool = True,
    load_developed_self: bool = True,
    load_preference_promotion: bool = True,
) -> Mary:
    """
    Construct a Mary coordinator with durable memory enabled.

    ``Mary()`` intentionally remains a low-level, side-effect-light
    coordinator constructor so unit tests and dependency-injection callers do
    not silently read or write the creator's real memory files.  Scripts that
    want a standalone Mary object *with* the same persistence behavior as the
    canonical application runtime should use this factory instead.
    """

    return create_application(
        memory_path=memory_path,
        developed_self_path=developed_self_path,
        preference_promotion_path=preference_promotion_path,
        auto_save=auto_save,
        load_memory=load_memory,
        load_developed_self=load_developed_self,
        load_preference_promotion=load_preference_promotion,
        name="mary_persistent",
    ).mary


def create_application(
    *,
    mary: Mary | None = None,
    memory_path: str | Path | None = None,
    developed_self_path: str | Path | None = None,
    preference_promotion_path: str | Path | None = None,
    auto_save: bool = True,
    load_memory: bool = True,
    load_developed_self: bool = True,
    load_preference_promotion: bool = True,
    name: str = "mary",
) -> MaryApplication:
    """
    Construct the canonical full MaryV2 application runtime.

    Supplying an existing Mary instance is supported for tests and explicit
    dependency injection. No duplicate Mary object is created in that case.
    """

    mary = (
        mary
        if mary is not None
        else Mary()
    )

    mary.config.ensure_directories()

    resolved_memory_path = (
        Path(memory_path)
        if memory_path is not None
        else mary.config.paths.memory / "memory.json"
    )

    mary.memory.configure_persistence(
        resolved_memory_path,
        auto_save=auto_save,
        load=load_memory,
    )

    resolved_developed_self_path = (
        Path(developed_self_path)
        if developed_self_path is not None
        else mary.config.paths.memory.parent
        / "personality"
        / "developed_self.json"
    )

    mary.configure_developed_self_persistence(
        resolved_developed_self_path,
        auto_save=auto_save,
        load=load_developed_self,
    )

    resolved_preference_promotion_path = (
        Path(preference_promotion_path)
        if preference_promotion_path is not None
        else mary.config.paths.memory.parent
        / "personality"
        / "preference_promotion.json"
    )

    mary.configure_preference_promotion_persistence(
        resolved_preference_promotion_path,
        auto_save=auto_save,
        load=load_preference_promotion,
    )

    # Memory is loaded here, after Mary construction.  Give the relationship
    # system one conservative pass over durable explicit creator statements so
    # older V2 memories can populate the structured creator model without
    # promoting arbitrary conversation or inference.
    sync_relationship = getattr(
        mary,
        "_sync_relationship_from_existing_memories",
        None,
    )
    if callable(sync_relationship):
        sync_relationship()

    # Configure Mary 13.0 conversation engagement + development beside the
    # same data root as memory. Custom/test memory paths remain isolated.
    data_root = resolved_memory_path.parent.parent
    try:
        mary.engagement.configure(
            data_root / "runtime" / "conversation_engagement.json",
            auto_save=auto_save,
            load=True,
        )
    except Exception as exc:
        mary._engagement_startup_error = f"{type(exc).__name__}: {exc}"
    try:
        mary.growth.configure(
            data_root / "development",
            auto_save=auto_save,
            load=True,
        )
    except Exception as exc:
        mary._growth_startup_error = f"{type(exc).__name__}: {exc}"

    try:
        mary.training_feedback.configure(
            data_root / "training" / "response_feedback.json",
            load=True,
        )
    except Exception as exc:
        mary._training_feedback_startup_error = f"{type(exc).__name__}: {exc}"

    # Configure Mary's rebuildable local cognitive reservoir beside the same
    # data root as canonical memory. Custom/test memory paths therefore keep
    # reservoir files isolated automatically instead of touching real state.
    try:
        reservoir_storage = os.getenv("MARY_RESERVOIR_STORAGE", "persistent").strip().lower()
        if reservoir_storage in {"memory", "ephemeral", "temporary", "temp"}:
            mary.mind.configure_ephemeral(rebuild=True)
        else:
            reservoir_path = resolved_memory_path.parent.parent / "reservoir" / "mary_reservoir.sqlite3"
            mary.mind.configure_persistence(reservoir_path, rebuild=None)
    except Exception as exc:
        # The reservoir accelerates conversation but is never authoritative; a
        # failure must not prevent Mary from starting.
        mary._reservoir_startup_error = f"{type(exc).__name__}: {exc}"

    state = RuntimeState()

    stage = MaryStage(
        mary=mary,
    )

    pipeline = Pipeline(
        state,
        stages=[stage],
        name=name,
    )

    return MaryApplication(
        mary=mary,
        state=state,
        pipeline=pipeline,
        memory_path=resolved_memory_path,
        developed_self_path=resolved_developed_self_path,
        preference_promotion_path=resolved_preference_promotion_path,
    )


def run_interactive(
    application: MaryApplication | None = None,
) -> None:
    """
    Run the shared terminal interface used by every MaryV2 entry point.
    """

    print("=" * 60)
    print("MaryV2")
    print("=" * 60)

    try:
        app = (
            application
            if application is not None
            else create_application()
        )

    except Exception as exc:
        print()
        print("Mary failed to initialize.")
        print(f"{type(exc).__name__}: {exc}")
        return

    mary = app.mary

    print()
    print("Mary initialized successfully.")

    try:
        status = mary.status()

        print(
            f"Name: {status.get('name', 'Mary')}"
        )

        cognition = status.get(
            "cognition",
            {},
        )

        strategy = str(cognition.get("routing_strategy", "configured"))
        provider_order = cognition.get("provider_order", [])
        conversation_order = cognition.get("conversation_provider_order", [])

        if strategy == "free_first" and isinstance(provider_order, list):
            print(f"LLM Strategy: {strategy}")
            print("Task/General Route: " + " -> ".join(str(item) for item in provider_order))
            if isinstance(conversation_order, list) and conversation_order:
                print("Conversation Route: " + " -> ".join(str(item) for item in conversation_order))
            try:
                local_model = mary.llm.get_provider("ollama").model_name()
            except Exception:
                local_model = "unavailable"
            print(f"Local conversation engine: ollama / {local_model}")
        else:
            print(
                "LLM Provider: "
                f"{cognition.get('llm', 'unknown')}"
            )
            print(
                "LLM Model: "
                f"{cognition.get('model', 'unknown')}"
            )

    except Exception as exc:
        print(
            "Warning: Could not read full system status: "
            f"{type(exc).__name__}: {exc}"
        )

    print()
    try:
        print(format_live_state(app))
        print()
    except Exception as exc:
        print(f"Warning: Could not render live character state: {type(exc).__name__}: {exc}")
        print()
    print("Mary is ready.")
    print("At 'You:' type requests for Mary, not PowerShell commands.")
    print("Type '/help', '/state', '/resources', '/memory-status', '/route', '/conversation', '/growth', '/realtime', '/nodes', '/retrieval', '/environment', '/contract', '/audit', '/pending', '/last', or 'exit'.")
    print("=" * 60)
    print()

    last_result = None

    try:
        while True:

            try:
                user_input = input(
                    "You: "
                ).strip()

            except (
                EOFError,
                KeyboardInterrupt,
            ):
                print()
                break

            if not user_input:
                continue

            if user_input.lower() in {
                "exit",
                "quit",
            }:
                break

            command = user_input.lower()

            if command in {"/help", "/h"}:
                print(f"Mary: {interactive_help(app)}")
                continue

            if command in {"/pending", "pending", "pending requests"}:
                print(f"Mary: {format_pending_requests(app)}")
                continue

            if command in {"/last", "/debug", "last turn"}:
                print(format_last_turn(last_result))
                continue

            if command in {"/state", "state", "character state"}:
                print(format_live_state(app))
                continue

            if command in {"/resources", "/resource", "resources"}:
                print(format_resource_state(app))
                continue

            if command in {"/memory-status", "/memory", "memory status", "memory lifecycle"}:
                print(format_memory_status(app))
                continue

            if command in {"/route", "/model", "route", "model route"}:
                print(format_route_state(app))
                continue

            if command in {"/conversation", "/talk-status", "conversation mode", "talk status"}:
                print(format_conversation_state(app))
                continue

            if command in {"/talk", "talk mode"}:
                app.mary.engagement.begin_session("engaged", turns=8, reason="terminal command")
                print("Mary: Intentional conversation mode is active for the next 8 turns.")
                continue

            if command in {"/deep", "deep mode"}:
                app.mary.engagement.begin_session("deep", turns=10, reason="terminal command")
                print("Mary: Deep conversation mode is active for the next 10 turns.")
                continue

            if command in {"/auto", "/adaptive", "adaptive mode"}:
                app.mary.engagement.set_mode("adaptive")
                app.mary.engagement.end_session()
                print("Mary: Conversation mode is back to adaptive.")
                continue

            if command in {"/growth", "/development", "growth status", "development status"}:
                print(format_growth_state(app))
                continue

            if command in {"/realtime", "/attention", "realtime status", "attention status"}:
                print(format_realtime_state(app))
                continue

            if command in {"/nodes", "/node", "nodes", "compute nodes"}:
                print(format_nodes_state(app))
                continue

            if command in {"/retrieval", "/vectors", "retrieval status", "vector status"}:
                print(format_retrieval_state(app))
                continue

            if command in {"/environment", "/env", "/capabilities", "environment", "capabilities"}:
                print(format_environment_state(app))
                continue

            if command in {"/contract", "contract", "system contract", "architecture contract"}:
                print(format_system_contract(app))
                continue

            if command in {"/audit", "audit", "state audit"}:
                from mary.runtime.state_audit import format_creator_state_audit
                print(format_creator_state_audit(app.mary, show_all=False))
                continue

            if looks_like_terminal_command(user_input):
                print(f"Mary: {terminal_command_guidance(user_input)}")
                continue

            try:
                result = app.run(
                    user_input
                )
                last_result = result

                if result.success:
                    response = result.output

                    if response is None:
                        response = (
                            "[No response was generated.]"
                        )

                    print(
                        f"Mary: {response}"
                    )

                else:
                    print(
                        "Mary encountered an error: "
                        f"{result.error}"
                    )

            except KeyboardInterrupt:
                print()
                break

            except Exception as exc:
                print()
                print(
                    "[MaryV2 Error] "
                    f"{type(exc).__name__}: {exc}"
                )
                print()

    finally:
        app.close()

    print()
    print("Mary stopped.")