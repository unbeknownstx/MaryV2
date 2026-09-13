"""Frontier/open-model provider catalog for MaryV2.

This module is configuration metadata, not model authority. A catalog entry
describes how Mary may reach an inference service; it never changes Mary's
identity, memory, relationship state, or permission boundaries.

Model names are intentionally environment-overridable because frontier model
aliases move quickly. Provider-specific model licenses must be checked at the
model level before redistribution or self-hosting; an API preset does not imply
that every model served by that vendor has the same license. Compatibility
features are advertised conservatively: common chat-completions transport does
not imply support for every OpenAI extension such as strict JSON Schema.
"""
from __future__ import annotations

from dataclasses import dataclass

from .interface import GenerationCost


@dataclass(frozen=True)
class ProviderPreset:
    """Secret-free connection metadata for one OpenAI-compatible provider."""

    name: str
    vendor: str
    base_url: str
    api_key_envs: tuple[str, ...]
    model_env: str
    default_model: str
    base_url_env: str
    cost_class: str = GenerationCost.PAID_LOW.value
    structured_output: bool = False
    notes: str = ""

    def public_dict(self) -> dict[str, object]:
        """Return diagnostics-safe metadata; never read or expose key values."""
        return {
            "name": self.name,
            "vendor": self.vendor,
            "protocol": "openai_chat_completions",
            "base_url": self.base_url,
            "api_key_envs": list(self.api_key_envs),
            "model_env": self.model_env,
            "default_model": self.default_model,
            "base_url_env": self.base_url_env,
            "cost_class": self.cost_class,
            "structured_output": self.structured_output,
            "notes": self.notes,
        }


PROVIDER_PRESETS: dict[str, ProviderPreset] = {
    "deepseek": ProviderPreset(
        name="deepseek",
        vendor="DeepSeek",
        base_url="https://api.deepseek.com",
        api_key_envs=("DEEPSEEK_API_KEY",),
        model_env="MARY_DEEPSEEK_MODEL",
        default_model="deepseek-flash",
        base_url_env="MARY_DEEPSEEK_BASE_URL",
        notes="Direct DeepSeek route; model alias remains environment-overridable.",
    ),
    "zai": ProviderPreset(
        name="zai",
        vendor="Z.AI / GLM",
        base_url="https://api.z.ai/api/paas/v4/",
        api_key_envs=("ZAI_API_KEY",),
        model_env="MARY_ZAI_MODEL",
        default_model="glm-5.3-flash",
        base_url_env="MARY_ZAI_BASE_URL",
        notes="Direct GLM route using Z.AI's OpenAI-compatible API.",
    ),
    "qwen_cloud": ProviderPreset(
        name="qwen_cloud",
        vendor="Alibaba Cloud / Qwen",
        base_url="https://dashscope-us.aliyuncs.com/compatible-mode/v1",
        api_key_envs=("QWEN_API_KEY", "DASHSCOPE_API_KEY"),
        model_env="MARY_QWEN_CLOUD_MODEL",
        default_model="qwen3.8-flash",
        base_url_env="MARY_QWEN_CLOUD_BASE_URL",
        notes="US Model Studio endpoint by default; override for another region/workspace.",
    ),
    "kimi": ProviderPreset(
        name="kimi",
        vendor="Moonshot AI / Kimi",
        base_url="https://api.moonshot.ai/v1",
        api_key_envs=("MOONSHOT_API_KEY", "KIMI_API_KEY"),
        model_env="MARY_KIMI_MODEL",
        default_model="kimi-k3",
        base_url_env="MARY_KIMI_BASE_URL",
        notes="Direct Kimi Open Platform route; model alias remains environment-overridable.",
    ),
    "minimax": ProviderPreset(
        name="minimax",
        vendor="MiniMax",
        base_url="https://api.minimax.io/v1",
        api_key_envs=("MINIMAX_API_KEY",),
        model_env="MARY_MINIMAX_MODEL",
        default_model="MiniMax-M3",
        base_url_env="MARY_MINIMAX_BASE_URL",
        notes="Direct MiniMax OpenAI-compatible text route.",
    ),
    "cerebras": ProviderPreset(
        name="cerebras",
        vendor="Cerebras Inference",
        base_url="https://api.cerebras.ai/v1",
        api_key_envs=("CEREBRAS_API_KEY",),
        model_env="MARY_CEREBRAS_MODEL",
        default_model="gpt-oss-120b",
        base_url_env="MARY_CEREBRAS_BASE_URL",
        notes="Fast hosted open-model inference; model alias may evolve.",
    ),
    "together": ProviderPreset(
        name="together",
        vendor="Together AI",
        base_url="https://api.together.ai/v1",
        api_key_envs=("TOGETHER_API_KEY",),
        model_env="MARY_TOGETHER_MODEL",
        default_model="openai/gpt-oss-120b",
        base_url_env="MARY_TOGETHER_BASE_URL",
        notes="Hosted open-model catalog through Together's compatible endpoint.",
    ),
    "fireworks": ProviderPreset(
        name="fireworks",
        vendor="Fireworks AI",
        base_url="https://api.fireworks.ai/inference/v1",
        api_key_envs=("FIREWORKS_API_KEY",),
        model_env="MARY_FIREWORKS_MODEL",
        default_model="accounts/fireworks/models/deepseek-v3p1",
        base_url_env="MARY_FIREWORKS_BASE_URL",
        notes="Hosted open-model inference; model is explicitly overrideable.",
    ),
}

FRONTIER_PROVIDER_NAMES: tuple[str, ...] = tuple(PROVIDER_PRESETS)


def get_provider_preset(name: str) -> ProviderPreset | None:
    return PROVIDER_PRESETS.get(str(name or "").strip().lower())


def public_provider_catalog() -> list[dict[str, object]]:
    """Return deterministic diagnostics/documentation metadata without secrets."""
    return [PROVIDER_PRESETS[name].public_dict() for name in FRONTIER_PROVIDER_NAMES]
