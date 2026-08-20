from __future__ import annotations

import pytest

from mary.core.config import Config
from mary.core.mary import Mary
from mary.llm.interface import LLMInterface, LLMResponse
from mary.llm.router import LLMRouter
from mary.orchestration import (
    OrchestrationRoute,
    PrivacyMode,
    TaskOrchestrator,
    TaskWorkspaceManager,
)


class CountingProvider(LLMInterface):
    def __init__(self, name: str):
        self.name = name
        self.calls = 0

    def generate(self, messages, temperature=0.7, max_tokens=2048):
        self.calls += 1
        return LLMResponse(
            content="should not be called by planning",
            provider=self.name,
            model="fake",
        )

    def is_available(self):
        return True

    def provider_name(self):
        return self.name

    def model_name(self):
        return "fake"


def _orchestrator():
    router = LLMRouter(Config())
    providers = {
        name: CountingProvider(name)
        for name in ("groq", "gemini", "openrouter", "ollama", "openai")
    }
    for name, provider in providers.items():
        router.register_provider(name, provider)
    workspace = TaskWorkspaceManager()
    return TaskOrchestrator(workspace=workspace, router=router), workspace, providers


def test_planning_is_deterministic_and_does_not_call_any_provider():
    orchestrator, workspace, providers = _orchestrator()
    task = workspace.create_task("Draft a concise explanation")

    plan = orchestrator.plan(task.task_id)

    assert plan.route == OrchestrationRoute.FREE_GENERATION.value
    assert plan.provider_route == "free_first"
    assert all(provider.calls == 0 for provider in providers.values())
    assert task.decisions[-1].status == "planned"


def test_private_task_forces_local_private_generation():
    orchestrator, workspace, _ = _orchestrator()
    task = workspace.create_task("Review this private memory")

    plan = orchestrator.plan(task.task_id)

    assert plan.privacy == PrivacyMode.LOCAL_ONLY.value
    assert plan.route == OrchestrationRoute.PRIVATE_GENERATION.value
    assert plan.provider_route == "private"
    assert plan.cost_class == "zero_local"


def test_explicit_local_capability_stays_deterministic_and_zero_cost():
    orchestrator, workspace, _ = _orchestrator()
    task = workspace.create_task(
        "Read Mary's runtime state",
        metadata={"local_capable": True},
    )

    plan = orchestrator.plan(task.task_id)

    assert plan.route == OrchestrationRoute.LOCAL.value
    assert plan.capability == "deterministic"
    assert plan.cost_class == "zero_local"


def test_current_information_prefers_research_not_model_guessing():
    orchestrator, workspace, _ = _orchestrator()
    task = workspace.create_task("Find the latest provider documentation")

    plan = orchestrator.plan(task.task_id)

    assert plan.route == OrchestrationRoute.RESEARCH.value
    assert plan.capability == "research"
    assert "current/external information" in " ".join(plan.rationale)


def test_verification_route_prioritizes_evidence_over_model_opinion():
    orchestrator, workspace, _ = _orchestrator()
    task = workspace.create_task("Run tests and verify the routing guarantee")

    plan = orchestrator.plan(task.task_id)

    assert plan.route == OrchestrationRoute.VERIFY.value
    assert plan.should_verify is True
    assert plan.capability == "verification"


def test_paid_expert_is_blocked_without_explicit_task_opt_in():
    orchestrator, workspace, _ = _orchestrator()
    task = workspace.create_task(
        "Critique this difficult architecture",
        metadata={"needs_expert": True},
    )

    plan = orchestrator.plan(task.task_id)

    assert plan.route == OrchestrationRoute.FREE_GENERATION.value
    assert plan.paid_allowed is False
    assert plan.cost_class == "free_cloud"
    assert "paid use is not authorized" in " ".join(plan.rationale).lower()


def test_paid_expert_requires_explicit_opt_in_and_uses_expert_route():
    orchestrator, workspace, _ = _orchestrator()
    task = workspace.create_task(
        "Critique this difficult architecture",
        metadata={"needs_expert": True, "allow_paid": True},
    )

    plan = orchestrator.plan(task.task_id)

    assert plan.route == OrchestrationRoute.EXPERT.value
    assert plan.provider_route == "expert"
    assert plan.cost_class == "paid_low"
    assert plan.paid_allowed is True


def test_private_context_beats_paid_expert_request():
    orchestrator, workspace, _ = _orchestrator()
    task = workspace.create_task(
        "Review my API key handling",
        metadata={"needs_expert": True, "allow_paid": True},
    )

    plan = orchestrator.plan(task.task_id)

    assert plan.privacy == PrivacyMode.LOCAL_ONLY.value
    assert plan.route == OrchestrationRoute.PRIVATE_GENERATION.value
    assert plan.provider_route == "private"


def test_consequential_creator_authority_routes_to_human_decision():
    orchestrator, workspace, _ = _orchestrator()
    task = workspace.create_task("Change Mary's values to match a model suggestion")

    plan = orchestrator.plan(task.task_id)

    assert plan.route == OrchestrationRoute.HUMAN_DECISION.value
    assert plan.requires_approval is True
    assert plan.capability == "human_judgment"


def test_redact_first_preserves_cloud_option_but_requires_boundary_review():
    orchestrator, workspace, _ = _orchestrator()
    task = workspace.create_task("Summarize selected project context")

    plan = orchestrator.plan(
        task.task_id,
        privacy="redact_first",
    )

    assert plan.route == OrchestrationRoute.FREE_GENERATION.value
    assert plan.privacy == PrivacyMode.REDACT_FIRST.value
    assert plan.requires_approval is True


def test_closed_task_cannot_be_replanned():
    orchestrator, workspace, _ = _orchestrator()
    task = workspace.create_task("Temporary")
    workspace.complete(task.task_id)

    with pytest.raises(RuntimeError):
        orchestrator.plan(task.task_id)


def test_mary_exposes_task_orchestrator_runtime_policy():
    mary = Mary()

    status = mary.status()["orchestration"]["task_orchestrator"]

    assert mary.task_orchestrator.workspace is mary.task_workspace
    assert mary.task_orchestrator.router is mary.llm
    assert status["planning"] == "deterministic"
    assert status["paid_policy"] == "explicit_task_opt_in"
    assert status["execution_policy"] == "plan_only_no_silent_execution"
