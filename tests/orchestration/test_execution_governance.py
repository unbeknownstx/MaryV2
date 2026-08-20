from __future__ import annotations

from mary.core.config import Config
from mary.llm.interface import LLMInterface, LLMResponse
from mary.llm.router import LLMRouter
from mary.orchestration.consultation import ExpertConsultant
from mary.orchestration.execution import ExecutionStatus, OrchestrationExecutor
from mary.orchestration.orchestrator import OrchestrationRoute, TaskOrchestrator
from mary.orchestration.workspace import TaskWorkspaceManager


class Provider(LLMInterface):
    def __init__(self, name): self.name=name; self.calls=0
    def generate(self, messages, temperature=0.7, max_tokens=2048):
        self.calls += 1
        return LLMResponse(content="useful result", provider=self.name, model="fake")
    def is_available(self): return True
    def provider_name(self): return self.name
    def model_name(self): return "fake"


def _system():
    config = Config()
    router = LLMRouter(config)
    for name in ("groq", "gemini", "openrouter", "ollama", "openai"):
        router.register_provider(name, Provider(name))
    workspace = TaskWorkspaceManager(limits=config.governance)
    expert = ExpertConsultant(router, workspace)
    planner = TaskOrchestrator(workspace=workspace, router=router)
    executor = OrchestrationExecutor(router=router, workspace=workspace, expert=expert)
    return planner, executor, workspace, router


def test_tool_plan_does_not_execute_without_explicit_host_handler():
    planner, executor, workspace, _ = _system()
    task = workspace.create_task("inspect a file", metadata={"requires_tool": True})
    plan = planner.plan(task.task_id)
    result = executor.execute(plan)
    assert result.status == ExecutionStatus.NEEDS_HANDLER.value
    assert task.actions == []


def test_verification_handler_becomes_high_confidence_test_evidence():
    planner, executor, workspace, _ = _system()
    task = workspace.create_task("run tests and verify it")
    plan = planner.plan(task.task_id)
    result = executor.execute(plan, handlers={"verify": lambda _: "23 tests passed"})
    assert result.success
    assert task.evidence[-1].provenance == "test_result"
    assert task.evidence[-1].confidence == 1.0


def test_private_generation_uses_only_ollama():
    planner, executor, workspace, router = _system()
    task = workspace.create_task("review this private memory")
    plan = planner.plan(task.task_id)
    result = executor.execute(plan)
    assert result.success
    assert result.source == "ollama"
    assert router.providers["ollama"].calls == 1
    assert router.providers["groq"].calls == 0


def test_human_authority_route_never_silently_executes():
    planner, executor, workspace, _ = _system()
    task = workspace.create_task("change Mary's values to match a model suggestion")
    result = executor.execute(planner.plan(task.task_id))
    assert result.status == ExecutionStatus.NEEDS_APPROVAL.value



def test_unauthorized_expert_request_downgrades_without_calling_openai():
    planner, executor, workspace, router = _system()
    task = workspace.create_task(
        "critique this architecture",
        metadata={"needs_expert": True, "allow_paid": False},
    )

    plan = planner.plan(task.task_id)

    assert plan.route == OrchestrationRoute.FREE_GENERATION.value
    assert plan.provider_route == "free_first"
    assert plan.paid_allowed is False
    assert router.providers["openai"].calls == 0
    assert router.resource_governor.paid_calls == 0


def test_forced_expert_route_is_blocked_when_paid_allowed_is_false():
    from dataclasses import replace

    planner, executor, workspace, router = _system()
    task = workspace.create_task("paid expert boundary")
    base = planner.plan(task.task_id)
    forced = replace(
        base,
        route=OrchestrationRoute.EXPERT.value,
        provider_route="expert",
        capability="expert_reasoning",
        cost_class="paid_low",
        paid_allowed=False,
        requires_approval=False,
    )

    result = executor.execute(forced)

    assert result.status == ExecutionStatus.BLOCKED.value
    assert router.providers["openai"].calls == 0
    assert router.resource_governor.paid_calls == 0
