from __future__ import annotations

from types import SimpleNamespace

from mary.governance.limits import RuntimeLimits

from mary.core.service import MaryCoreService
from mary.distributed import CapabilityDescriptor, NodeDescriptor, NodeRegistry
from mary.llm.interface import LLMMessage, LLMResponse
from mary.llm.router import LLMRouter


class _Config:
    class LLM:
        provider = "ollama"
        fallback_providers = []
        free_provider_order = ["ollama"]
        conversation_provider_order = ["ollama"]
        routing_strategy = "free_first"
        temperature = 0.7
        max_tokens = 128
        expert_provider = "openai"
        rate_limit_cooldown_seconds = 300.0
        openai_model = "unused"
        openai_reasoning_effort = "low"
        model = "unused"

    llm = LLM()
    governance = RuntimeLimits()


class _Provider:
    def is_available(self):
        return True

    def provider_name(self):
        return "ollama"

    def model_name(self):
        return "test-local-role"

    def generate(self, messages, temperature=0.7, max_tokens=128):
        return LLMResponse(content="hello", provider="ollama", model="test-local-role")


def test_router_status_reports_routes_without_authority_claims(monkeypatch):
    router = LLMRouter(_Config())
    router.register_provider("ollama", _Provider())
    status = router.routing_status()
    assert status["routes"]["private"] == ["ollama"]
    assert status["providers"][0]["available"] is True
    assert "identity/state authority" in status["policy"]


def test_successful_generation_records_selected_engine():
    router = LLMRouter(_Config())
    router.register_provider("ollama", _Provider())
    response = router.generate([LLMMessage(role="user", content="hi")], route="private")
    assert response.content == "hello"
    status = router.routing_status()["last_generation"]
    assert status["status"] == "success"
    assert status["selected_provider"] == "ollama"
    assert status["selected_model"] == "test-local-role"
    assert status["order"] == ["ollama"]


def test_node_registry_preview_keeps_execution_unauthorized():
    registry = NodeRegistry(stale_after=90)
    cap = CapabilityDescriptor(name="llm.ollama", local=True, private=True, cost="local")
    registry.register(NodeDescriptor(
        node_id="pc-node",
        display_name="PC Node",
        role="capability_node",
        host_type="windows",
        platform="win32",
        capabilities={"llm.ollama": cap},
        local=False,
        trusted=True,
        surface="headless",
        transport="http",
    ))
    preview = registry.route_preview("llm.ollama")
    assert preview["available"] is True
    assert preview["selected_node_id"] == "pc-node"
    assert preview["execution"] == "not_authorized"


def test_core_compute_fabric_is_display_safe_and_preserves_authority():
    service = MaryCoreService.__new__(MaryCoreService)
    service.device_tasks = SimpleNamespace(snapshot=lambda: {"queued": 0, "claimed": 0, "tasks": []})
    registry = NodeRegistry()
    router = SimpleNamespace(routing_status=lambda: {"strategy": "free_first", "providers": []})
    service.mary = SimpleNamespace(node_registry=registry, llm=router)
    status = service.compute_fabric_status()
    assert status["authority"] == "mary_core"
    assert status["private_route_ready"] is False
    assert "never transfers Mary identity" in status["policy"]
