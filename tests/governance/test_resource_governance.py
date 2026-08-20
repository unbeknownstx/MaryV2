from __future__ import annotations

import pytest

from mary.core.config import Config
from mary.governance.limits import RuntimeLimits
from mary.llm.interface import LLMInterface, LLMProviderError, LLMResponse
from mary.llm.router import LLMRouter
from mary.orchestration.consultation import ExpertConsultant
from mary.orchestration.workspace import TaskWorkspaceManager


class Provider(LLMInterface):
    def __init__(self, name: str, *, fail: bool = False):
        self.name = name
        self.fail = fail
        self.calls = 0

    def generate(self, messages, temperature=0.7, max_tokens=2048):
        self.calls += 1
        if self.fail:
            raise LLMProviderError("nope", provider=self.name, retryable=True)
        return LLMResponse(
            content=f"{self.name} ok",
            provider=self.name,
            model="fake",
            usage={"prompt_tokens": 10, "completion_tokens": 4},
        )

    def is_available(self): return True
    def provider_name(self): return self.name
    def model_name(self): return "fake"


def test_provider_attempt_ceiling_is_central_and_hard():
    config = Config()
    config.llm.routing_strategy = "configured"
    config.llm.provider = "a"
    config.llm.fallback_providers = ["b", "c"]
    config.governance = RuntimeLimits(provider_attempts_per_generation=2)
    router = LLMRouter(config)
    for name in ("a", "b", "c"):
        router.register_provider(name, Provider(name, fail=True))

    with pytest.raises(LLMProviderError):
        router.generate([])

    assert [x["provider"] for x in router.last_generation_attempts] == ["a", "b"]
    assert router.resource_governor.status()["provider_attempts"] == 2
    assert router.providers["c"].calls == 0


def test_resource_governor_tracks_tokens_without_prompt_content():
    config = Config()
    config.llm.provider = "fake"
    config.llm.routing_strategy = "configured"
    router = LLMRouter(config)
    router.register_provider("fake", Provider("fake"))

    router.generate([])
    status = router.resource_governor.status()

    assert status["prompt_tokens"] == 10
    assert status["completion_tokens"] == 4
    assert "SECRET_PROMPT_BODY" not in str(status)
    assert "messages" not in status["last_generation"]


def test_paid_expert_requires_task_authorization_and_is_one_call_by_default():
    config = Config()
    config.llm.expert_provider = "openai"
    router = LLMRouter(config)
    provider = Provider("openai")
    router.register_provider("openai", provider)
    workspace = TaskWorkspaceManager(limits=config.governance)
    consultant = ExpertConsultant(router, workspace)

    blocked = workspace.create_task("expert review")
    with pytest.raises(PermissionError):
        consultant.consult(blocked.task_id, "review")
    assert provider.calls == 0

    allowed = workspace.create_task("expert review", metadata={"allow_paid": True})
    consultant.consult(allowed.task_id, "review")
    assert provider.calls == 1
    with pytest.raises(RuntimeError):
        consultant.consult(allowed.task_id, "review again")
    assert provider.calls == 1
