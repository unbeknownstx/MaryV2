"""
MaryV2 Configuration

Central configuration for the Mary runtime.

Configuration is intentionally kept separate from the systems that consume it.
This allows providers, paths, and runtime behavior to change without modifying
the architecture itself.
"""

from dataclasses import dataclass, field
from pathlib import Path
import os

from dotenv import load_dotenv


load_dotenv()


@dataclass
class LLMConfig:
    """Configuration for the language model layer."""

    provider: str = "groq"
    model: str = "openai/gpt-oss-20b"
    temperature: float = 0.7
    max_tokens: int = 2048
    fallback_providers: list[str] = field(default_factory=list)
    routing_strategy: str = "free_first"
    free_provider_order: list[str] = field(
        default_factory=lambda: [
            "groq",
            "gemini",
            "openrouter",
            "ollama",
        ]
    )
    rate_limit_cooldown_seconds: float = 300.0
    expert_provider: str = "openai"
    openai_model: str = "gpt-5.6-luna"
    openai_reasoning_effort: str = "low"


@dataclass
class PathConfig:
    """Filesystem locations used by Mary."""

    root: Path = field(
        default_factory=lambda: Path(__file__).resolve().parents[2]
    )

    @property
    def data(self) -> Path:
        return self.root / "data"

    @property
    def identity(self) -> Path:
        return self.data / "identity"

    @property
    def personality(self) -> Path:
        return self.data / "personality"

    @property
    def memory(self) -> Path:
        return self.data / "memory"

    @property
    def relationship(self) -> Path:
        return self.data / "relationship"

    @property
    def knowledge(self) -> Path:
        return self.data / "knowledge"

    @property
    def goals(self) -> Path:
        return self.data / "goals"

    @property
    def learning(self) -> Path:
        return self.data / "learning"

    @property
    def runtime(self) -> Path:
        return self.data / "runtime"


@dataclass
class RuntimeConfig:
    """Configuration for Mary's runtime behavior."""

    environment: str = "development"
    debug: bool = True
    autonomous: bool = True


@dataclass
class Config:
    """
    Root configuration object for MaryV2.

    Configuration can eventually be loaded from environment variables,
    configuration files, or another configuration provider without
    changing the rest of Mary's architecture.
    """

    application_name: str = "Mary"
    version: str = "2.0.0"

    llm: LLMConfig = field(
        default_factory=LLMConfig
    )

    paths: PathConfig = field(
        default_factory=PathConfig
    )

    runtime: RuntimeConfig = field(
        default_factory=RuntimeConfig
    )

    @classmethod
    def from_environment(cls):
        """
        Create configuration using environment variables where available.

        Existing defaults remain intact when variables are not provided.
        """

        config = cls()

        config.llm.provider = os.getenv(
            "MARY_LLM_PROVIDER",
            config.llm.provider
        )

        config.llm.model = os.getenv(
            "MARY_LLM_MODEL",
            config.llm.model
        )

        fallback_value = os.getenv("MARY_LLM_FALLBACKS", "")
        config.llm.fallback_providers = [
            item.strip().lower()
            for item in fallback_value.split(",")
            if item.strip()
        ]

        config.llm.routing_strategy = os.getenv(
            "MARY_LLM_ROUTING_STRATEGY",
            config.llm.routing_strategy,
        ).strip().lower()

        free_order_value = os.getenv(
            "MARY_LLM_FREE_ORDER",
            "",
        )
        if free_order_value.strip():
            config.llm.free_provider_order = [
                item.strip().lower()
                for item in free_order_value.split(",")
                if item.strip()
            ]

        config.llm.expert_provider = os.getenv(
            "MARY_LLM_EXPERT_PROVIDER",
            config.llm.expert_provider,
        ).strip().lower() or config.llm.expert_provider

        config.llm.openai_model = os.getenv(
            "MARY_OPENAI_MODEL",
            config.llm.openai_model,
        ).strip() or config.llm.openai_model

        reasoning_effort = os.getenv(
            "MARY_OPENAI_REASONING_EFFORT",
            config.llm.openai_reasoning_effort,
        ).strip().lower()
        if reasoning_effort in {"none", "low", "medium", "high", "xhigh", "max"}:
            config.llm.openai_reasoning_effort = reasoning_effort

        cooldown_value = os.getenv(
            "MARY_LLM_RATE_LIMIT_COOLDOWN",
        )
        if cooldown_value is not None:
            try:
                config.llm.rate_limit_cooldown_seconds = max(
                    0.0,
                    float(cooldown_value),
                )
            except ValueError:
                pass

        config.runtime.environment = os.getenv(
            "MARY_ENVIRONMENT",
            config.runtime.environment
        )

        debug_value = os.getenv(
            "MARY_DEBUG"
        )

        if debug_value is not None:
            config.runtime.debug = (
                debug_value.lower()
                in {"1", "true", "yes", "on"}
            )

        autonomous_value = os.getenv(
            "MARY_AUTONOMOUS"
        )

        if autonomous_value is not None:
            config.runtime.autonomous = (
                autonomous_value.lower()
                in {"1", "true", "yes", "on"}
            )

        return config

    def ensure_directories(self):
        """Create Mary's persistent data directories."""

        directories = [
            self.paths.data,
            self.paths.identity,
            self.paths.personality,
            self.paths.memory,
            self.paths.relationship,
            self.paths.knowledge,
            self.paths.goals,
            self.paths.learning,
            self.paths.runtime,
        ]

        for directory in directories:
            directory.mkdir(
                parents=True,
                exist_ok=True
            )