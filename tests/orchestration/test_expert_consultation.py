from __future__ import annotations

from mary.core.config import Config
from mary.llm.interface import LLMInterface, LLMResponse
from mary.llm.router import LLMRouter
from mary.orchestration import ExpertConsultant, TaskWorkspaceManager


class FakeExpert(LLMInterface):
    def __init__(self):
        self.calls = 0
        self.messages = None

    def generate(self, messages, temperature=0.7, max_tokens=2048):
        self.calls += 1
        self.messages = messages
        return LLMResponse(
            content="Keep the stable core and test the boundary.",
            provider="openai",
            model="fake-openai",
            finish_reason="stop",
            usage={"prompt_tokens": 50, "completion_tokens": 20},
        )

    def is_available(self):
        return True

    def provider_name(self):
        return "openai"

    def model_name(self):
        return "fake-openai"


def _consultant():
    config = Config()
    config.llm.routing_strategy = "free_first"
    config.llm.expert_provider = "openai"
    router = LLMRouter(config)
    expert = FakeExpert()
    router.register_provider("openai", expert)
    workspace = TaskWorkspaceManager()
    return ExpertConsultant(router, workspace), workspace, expert, router


def test_expert_route_is_openai_only_and_does_not_enter_free_first():
    consultant, workspace, expert, router = _consultant()

    assert router._provider_order(None) == [
        "groq", "gemini", "openrouter", "ollama"
    ]
    assert router._provider_order(None, route="expert") == ["openai"]


def test_consultation_records_advisory_result_and_explicit_provenance():
    consultant, workspace, expert, router = _consultant()
    task = workspace.create_task("Review Mary's orchestration boundary")
    workspace.add_evidence(
        task.task_id,
        "The deterministic suite is green.",
        provenance="test_result",
        confidence=1.0,
    )

    result = consultant.consult(
        task.task_id,
        "What could still break?",
        context=["Preserve Mary's stable core."],
    )

    assert result.provider == "openai"
    assert expert.calls == 1
    assert len(task.consultations) == 1
    assert task.consultations[0].source == "openai"
    assert len(task.evidence) == 2
    assert task.evidence[-1].provenance == "openai"
    assert task.evidence[-1].metadata["advisory_only"] is True
    assert router.last_generation_attempts == [
        {"provider": "openai", "status": "success", "error": ""},
    ]


def test_consultation_prompt_is_bounded_to_task_context_not_mary_memory():
    consultant, workspace, expert, router = _consultant()
    task = workspace.create_task("Check one isolated claim")

    consultant.consult(
        task.task_id,
        "Review it.",
        context=["Only this explicit context may leave the process."],
    )

    combined = "\n".join(message.content for message in expert.messages)
    assert "Only this explicit context" in combined
    assert "persistent memory" not in combined.lower()
    assert "creator model" in expert.messages[0].content.lower()
