"""Display-safe MaryV2 architecture/authority contract.

The contract is intentionally descriptive rather than another state owner.  It
lets diagnostics and acceptance tests prove that the parts which *are* owners
remain connected to the same live Mary runtime after refactors.
"""

from __future__ import annotations

from typing import Any


class MarySystemContract:
    VERSION = "v2-breakthrough-12.9-uplift"

    AUTHORITY = {
        "character_canon": "mary.character + identity/biography/personality authored state",
        "creator_relationship": "RelationshipManager/UserModel",
        "memory": "MemoryManager",
        "emotion": "EmotionManager",
        "agency": "Agency",
        "conversation_continuity": "TurnMindState/ConversationContinuity",
        "relationship_question_continuity": "ConversationLearningBridge (process-local pending question; durable learning remains RelationshipManager)",
        "provider_routing": "LLMRouter",
        "host_capabilities": "RuntimeEnvironment (process-local; no identity ownership)",
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
        return issues
