from __future__ import annotations

from mary.core.config import Config
from mary.llm.interface import (
    GenerationCost,
    GenerationPrivacy,
    LLMInterface,
    LLMMessage,
    LLMResponse,
    ProviderRoute,
)
from mary.llm.provider_catalog import FRONTIER_PROVIDER_NAMES, public_provider_catalog
from mary.llm.providers.openai_compatible import OpenAICompatibleProvider
from mary.llm.router import LLMRouter
from mary.runtime.environment import RuntimeEnvironment
from mary.runtime.introspection import RuntimeIntrospection


class FakeProvider(LLMInterface):
    def __init__(self, name: str, *, available: bool = True, paid: bool = False):
        self.name = name
        self.available = available
        self.calls = 0
        self.paid = paid
        self.last_max_tokens = None

    def route_capabilities(self):
        return ProviderRoute(
            cost_class=(
                GenerationCost.PAID_LOW.value
                if self.paid
                else GenerationCost.FREE_CLOUD.value
            ),
        )

    def generate(self, messages, temperature=0.7, max_tokens=2048):
        self.calls += 1
        self.last_max_tokens = max_tokens
        return LLMResponse(
            content=f"{self.name} response",
            provider=self.name,
            model=f"fake-{self.name}",
        )

    def is_available(self):
        return self.available

    def provider_name(self):
        return self.name

    def model_name(self):
        return f"fake-{self.name}"


def _message():
    return [LLMMessage(role="user", content="frontier route test")]


def test_catalog_contains_current_frontier_provider_families():
    assert FRONTIER_PROVIDER_NAMES == (
        "deepseek",
        "zai",
        "qwen_cloud",
        "kimi",
        "minimax",
        "cerebras",
        "together",
        "fireworks",
    )
    rows = public_provider_catalog()
    assert [row["name"] for row in rows] == list(FRONTIER_PROVIDER_NAMES)
    assert all("api_key_envs" in row for row in rows)
    assert all("api_key" not in row for row in rows)


def test_named_openai_compatible_provider_is_lazy_and_key_gated(monkeypatch):
    monkeypatch.setenv("DEEPSEEK_API_KEY", "test-only-key")
    monkeypatch.setenv("MARY_DEEPSEEK_MODEL", "deepseek-v4-pro")
    router = LLMRouter(Config())

    provider = router.get_provider("deepseek")

    assert provider.provider_name() == "deepseek"
    assert provider.model_name() == "deepseek-v4-pro"
    assert provider.is_available() is True
    route = provider.route_capabilities()
    assert route.cost_class == GenerationCost.PAID_LOW.value
    assert GenerationPrivacy.LOCAL_ONLY.value not in route.privacy_modes


def test_custom_openai_compatible_loopback_can_be_zero_cost_and_private(monkeypatch):
    monkeypatch.delenv("MARY_OPENAI_COMPAT_API_KEY", raising=False)
    monkeypatch.setenv("MARY_OPENAI_COMPAT_BASE_URL", "http://127.0.0.1:9000/v1")
    monkeypatch.setenv("MARY_OPENAI_COMPAT_MODEL", "local-test")
    provider = OpenAICompatibleProvider()

    assert provider.is_available() is True
    route = provider.route_capabilities()
    assert route.cost_class == GenerationCost.ZERO_LOCAL.value
    assert GenerationPrivacy.LOCAL_ONLY.value in route.privacy_modes


def test_custom_remote_openai_compatible_requires_a_key(monkeypatch):
    monkeypatch.delenv("MARY_OPENAI_COMPAT_API_KEY", raising=False)
    monkeypatch.setenv("MARY_OPENAI_COMPAT_BASE_URL", "https://example.invalid/v1")
    monkeypatch.setenv("MARY_OPENAI_COMPAT_MODEL", "future-model")
    provider = OpenAICompatibleProvider()

    assert provider.is_available() is False


def test_frontier_route_uses_configured_opt_in_order():
    config = Config()
    config.llm.frontier_provider_order = ["deepseek", "zai", "openai"]
    router = LLMRouter(config)
    deepseek = FakeProvider("deepseek", available=False, paid=True)
    zai = FakeProvider("zai", paid=True)
    openai = FakeProvider("openai", paid=True)
    router.register_provider("deepseek", deepseek)
    router.register_provider("zai", zai)
    router.register_provider("openai", openai)

    response = router.generate(_message(), route="frontier")

    assert response.provider == "zai"
    assert deepseek.calls == 0
    assert zai.calls == 1
    assert openai.calls == 0


def test_free_first_never_silently_adds_frontier_paid_providers():
    config = Config()
    config.llm.provider = "deepseek"
    config.llm.routing_strategy = "free_first"
    router = LLMRouter(config)
    providers = {
        name: FakeProvider(name, paid=(name == "deepseek"))
        for name in ("groq", "gemini", "openrouter", "ollama", "deepseek")
    }
    for name, provider in providers.items():
        router.register_provider(name, provider)

    response = router.generate(_message())

    assert response.provider == "groq"
    assert providers["deepseek"].calls == 0
    assert "deepseek" not in [
        item["provider"] for item in router.last_generation_attempts
    ]


def test_expert_provider_can_be_a_frontier_provider():
    config = Config()
    config.llm.expert_provider = "deepseek"
    router = LLMRouter(config)
    deepseek = FakeProvider("deepseek", paid=True)
    router.register_provider("deepseek", deepseek)

    response = router.generate(_message(), route="expert")

    assert response.provider == "deepseek"
    assert deepseek.calls == 1



def test_frontier_order_can_be_configured_from_environment(monkeypatch):
    monkeypatch.setenv(
        "MARY_LLM_FRONTIER_ORDER",
        "kimi,deepseek,zai,openai",
    )

    config = Config.from_environment()

    assert config.llm.frontier_provider_order == [
        "kimi",
        "deepseek",
        "zai",
        "openai",
    ]


def test_runtime_environment_exposes_frontier_capability_names(monkeypatch):
    for key in (
        "DEEPSEEK_API_KEY",
        "ZAI_API_KEY",
        "QWEN_API_KEY",
        "DASHSCOPE_API_KEY",
        "MOONSHOT_API_KEY",
        "KIMI_API_KEY",
        "MINIMAX_API_KEY",
        "CEREBRAS_API_KEY",
        "TOGETHER_API_KEY",
        "FIREWORKS_API_KEY",
    ):
        monkeypatch.delenv(key, raising=False)
    monkeypatch.setenv("MARY_OLLAMA_ENABLED", "false")
    config = Config()
    router = LLMRouter(config)

    snapshot = RuntimeEnvironment(config=config, router=router).provider_snapshot()

    for name in FRONTIER_PROVIDER_NAMES:
        assert name in snapshot
        assert snapshot[name]["configured"] is False
        assert snapshot[name]["available"] is False


def test_runtime_introspection_recognizes_frontier_aliases():
    introspection = RuntimeIntrospection()

    assert introspection.classify("Can you use DeepSeek?").provider == "deepseek"
    assert introspection.classify("Can you use Qwen?").provider == "qwen_cloud"
    assert introspection.classify("Can you use GLM?").provider == "zai"
    assert introspection.classify("Can you use Kimi?").provider == "kimi"



def test_frontier_route_gets_larger_bounded_token_budget():
    config = Config()
    config.llm.frontier_provider_order = ["deepseek"]
    router = LLMRouter(config)
    deepseek = FakeProvider("deepseek", paid=True)
    router.register_provider("deepseek", deepseek)

    router.generate(_message(), route="frontier")

    assert deepseek.last_max_tokens == 8192
    assert router.last_generation_route["max_output_tokens"] == 8192


def test_frontier_requested_output_is_capped_by_governance():
    config = Config()
    config.llm.frontier_provider_order = ["deepseek"]
    router = LLMRouter(config)
    deepseek = FakeProvider("deepseek", paid=True)
    router.register_provider("deepseek", deepseek)

    router.generate(_message(), route="frontier", max_tokens=50000)

    assert deepseek.last_max_tokens == 8192
