"""Display-safe MaryV2 architecture/authority contract.

The contract is intentionally descriptive rather than another state owner.  It
lets diagnostics and acceptance tests prove that the parts which *are* owners
remain connected to the same live Mary runtime after refactors.
"""

from __future__ import annotations

from typing import Any


class MarySystemContract:
    VERSION = "v2-breakthrough-convergence-character-context-authority-1"

    AUTHORITY = {
        "character_canon": "mary.character bootstrap + CharacterSourcebook creator-authored evidence",
        "character_evaluation": "MaryEvaluationSet (acceptance evidence only; never identity/memory authority)",
        "root_authority": "MaryRootAuthority (executable hierarchy/invariants; no mutable state ownership)",
        "creator_relationship": "RelationshipManager/UserModel",
        "memory": "MemoryManager",
        "emotion": "EmotionManager",
        "agency": "Agency",
        "conversation_continuity": "TurnMindState/ConversationContinuity",
        "conversation_engagement": "ConversationEngagement (depth/initiative policy only; no identity ownership)",
        "relationship_question_continuity": "ConversationLearningBridge (process-local pending question; durable learning remains RelationshipManager)",
        "experience_development": "GrowthEngine + ExperienceJournal (grounded post-turn development; model dialogue is not durable self-evidence)",
        "provider_routing": "LLMRouter",
        "host_capabilities": "RuntimeEnvironment (process-local; no identity ownership)",
        "realtime_attention": "RealtimeInteractionCoordinator + AttentionBus (ephemeral priority/interruption state only)",
        "perception_boundary": "PerceptionDirector (objective environment context; no creator or memory authority)",
        "distributed_compute": "NodeRegistry (replaceable capability resources; never identity/state ownership)",
        "semantic_retrieval": "HybridReservoirRetriever + SemanticVectorIndex (derived candidate retrieval only)",
        "response_feedback": "ResponseFeedbackStore (explicit private evaluation/training data; never character-state authority)",
        "creative_production": "MaryEcosystem/ProductionStudio (canonical project artifacts only; never identity or automatic execution authority)",
        "creative_services": "CreativeServiceRegistry (secret-free capability/cost discovery only; no execution/spending authority)",
        "turn_routing_policy": "TurnPolicyEngine",
        "task_orchestration": "TaskOrchestrator + OrchestrationExecutor",
        "tools": "ToolManager",
        "durable_persistence": "owned subsystem stores via bounded atomic persistence",
        "final_authority": "creator/user for consequential external or durable changes",
    }

    def snapshot(self, mary: Any) -> dict[str, Any]:
        """Return a display-safe architecture snapshot without raw private data."""

        router = getattr(mary, "llm", None)
        reasoning = getattr(mary, "reasoning", None)
        reflection = getattr(mary, "reflection", None)
        task_orchestrator = getattr(mary, "task_orchestrator", None)
        task_executor = getattr(mary, "task_executor", None)
        expert = getattr(mary, "expert_consultant", None)
        emotion = getattr(mary, "emotion", None)
        avatar = getattr(mary, "avatar", None)
        runtime_environment = getattr(mary, "runtime_environment", None)
        sourcebook = getattr(mary, "character_sourcebook", None)
        character_evaluation = getattr(mary, "character_evaluation", None)
        root_authority = getattr(mary, "root_authority", None)

        shared_router = all(
            item is None or getattr(item, "router", getattr(item, "llm", None)) is router
            for item in (reasoning, reflection, task_orchestrator, task_executor, expert)
        )

        avatar_emotion = getattr(avatar, "emotion_manager", None)
        if avatar_emotion is None:
            avatar_emotion = getattr(avatar, "emotion", None)

        return {
            "connected": True,
            "version": self.VERSION,
            "authority": dict(self.AUTHORITY),
            "single_llm_router": bool(shared_router),
            "shared_emotion_state": avatar_emotion is None or avatar_emotion is emotion,
            "conversation_route": (
                router.conversation_provider_order()
                if callable(getattr(router, "conversation_provider_order", None))
                else []
            ),
            "task_route": (
                router._provider_order(None)
                if callable(getattr(router, "_provider_order", None))
                else []
            ),
            "effective_conversation_route": (
                runtime_environment.effective_provider_order(purpose="conversation")
                if callable(getattr(runtime_environment, "effective_provider_order", None))
                else []
            ),
            "effective_task_route": (
                runtime_environment.effective_provider_order(purpose=None)
                if callable(getattr(runtime_environment, "effective_provider_order", None))
                else []
            ),
            "host_type": (
                runtime_environment.host_type()
                if callable(getattr(runtime_environment, "host_type", None))
                else "unknown"
            ),
            "paid_openai_sticky": False,
            "background_browsing": False,
            "character_sourcebook": (
                sourcebook.snapshot()
                if callable(getattr(sourcebook, "snapshot", None))
                else {"enabled": False}
            ),
            "character_evaluation": (
                character_evaluation.snapshot()
                if callable(getattr(character_evaluation, "snapshot", None))
                else {"enabled": False}
            ),
            "root_authority": (
                root_authority.snapshot(mary)
                if callable(getattr(root_authority, "snapshot", None))
                else {"version": "missing"}
            ),
        }

    def validate(self, mary: Any) -> list[str]:
        snap = self.snapshot(mary)
        issues: list[str] = []
        if not snap.get("single_llm_router"):
            issues.append("model-backed subsystems do not share one LLMRouter")
        if not snap.get("shared_emotion_state"):
            issues.append("avatar/expression state is not sharing Mary's authoritative emotion manager")
        conversation = list(snap.get("conversation_route", []))
        if any(str(item).lower().strip() == "openai" for item in conversation):
            issues.append("paid OpenAI leaked into the normal conversation route")
        task = list(snap.get("task_route", []))
        if task and task[0] == "openai":
            issues.append("paid OpenAI leaked into the normal task route")
        root = getattr(mary, "root_authority", None)
        if callable(getattr(root, "validate", None)):
            issues.extend(str(item) for item in root.validate(mary))
        return list(dict.fromkeys(issues))
