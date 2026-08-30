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
import sys

from dotenv import load_dotenv

from mary.governance.limits import RuntimeLimits


def _resource_root() -> Path:
    bundled = getattr(sys, "_MEIPASS", None)
    if getattr(sys, "frozen", False) and bundled:
        return Path(bundled).resolve()
    return Path(__file__).resolve().parents[2]


def _executable_root() -> Path:
    if getattr(sys, "frozen", False):
        return Path(sys.executable).resolve().parent
    return _resource_root()


def _truthy_env(name: str) -> bool:
    return os.getenv(name, "").strip().lower() in {"1", "true", "yes", "on"}


def _platform_home() -> Path:
    """Return the home directory for the platform Mary is resolving.

    Tests intentionally simulate frozen Windows/macOS/Linux builds from a
    different host OS. ``Path.home()`` follows the *host* Python runtime, so a
    Windows test process pretending to be macOS would otherwise keep resolving
    ``C:\\Users\\...`` even after HOME is redirected. Prefer the
    platform-appropriate environment variable first and use ``Path.home()``
    only as the final host-native fallback.
    """

    if sys.platform == "win32":
        user_profile = os.getenv("USERPROFILE", "").strip()
        if user_profile:
            return Path(user_profile).expanduser()

        home_drive = os.getenv("HOMEDRIVE", "").strip()
        home_path = os.getenv("HOMEPATH", "").strip()
        if home_drive and home_path:
            return Path(home_drive + home_path).expanduser()

    else:
        home = os.getenv("HOME", "").strip()
        if home:
            return Path(home).expanduser()

    return Path.home()


def _platform_data_base() -> Path:
    """Return the host-native writable application-data directory.

    Frozen Mary builds must never write into PyInstaller's bundled resource
    tree. Windows uses LOCALAPPDATA, macOS uses Application Support, and
    Linux/Unix follows XDG_DATA_HOME when configured.
    """

    if sys.platform == "win32":
        local_app_data = os.getenv("LOCALAPPDATA", "").strip()
        if local_app_data:
            return Path(local_app_data).expanduser()
        return _platform_home() / "AppData" / "Local"

    if sys.platform == "darwin":
        return _platform_home() / "Library" / "Application Support"

    xdg_data_home = os.getenv("XDG_DATA_HOME", "").strip()
    if xdg_data_home:
        return Path(xdg_data_home).expanduser()
    return _platform_home() / ".local" / "share"


def _default_data_root(resource_root: Path) -> Path:
    """Return Mary's writable runtime-state root.

    Source checkouts are code, not Mary state containers.  Development runs use
    the same host-native application-data location as installed builds unless an
    explicit ``MARY_DATA_DIR`` or portable mode is requested.  This keeps test,
    conversation, relationship, and cache churn out of the Git working tree.
    """

    explicit = os.getenv("MARY_DATA_DIR", "").strip()
    if explicit:
        return Path(explicit).expanduser().resolve()
    if _truthy_env("MARY_PORTABLE"):
        return _executable_root() / "data"
    return _platform_data_base() / "MaryV2" / "data"


def _platform_config_base() -> Path:
    """Return a host-native private configuration directory."""

    if sys.platform == "win32":
        local_app_data = os.getenv("LOCALAPPDATA", "").strip()
        if local_app_data:
            return Path(local_app_data).expanduser()
        return _platform_home() / "AppData" / "Local"
    if sys.platform == "darwin":
        return _platform_home() / "Library" / "Application Support"
    xdg_config_home = os.getenv("XDG_CONFIG_HOME", "").strip()
    if xdg_config_home:
        return Path(xdg_config_home).expanduser()
    return _platform_home() / ".config"


def _dotenv_path() -> Path:
    explicit = os.getenv("MARY_ENV_FILE", "").strip()
    if explicit:
        return Path(explicit).expanduser()

    # Source/development runs continue to use the repository-local .env.
    if not getattr(sys, "frozen", False):
        return _resource_root() / ".env"

    # Portable builds intentionally keep all private state beside the app.
    if _truthy_env("MARY_PORTABLE"):
        return _executable_root() / ".env"

    # Preserve the original Windows behavior when a side-by-side .env already
    # exists, while giving fresh installs a user-writable configuration path.
    legacy = _executable_root() / ".env"
    if sys.platform == "win32" and legacy.exists():
        return legacy

    return _platform_config_base() / "MaryV2" / ".env"


load_dotenv(dotenv_path=_dotenv_path(), override=False)


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
    conversation_provider_order: list[str] = field(
        default_factory=lambda: [
            "ollama",
            "groq",
            "gemini",
            "openrouter",
        ]
    )
    rate_limit_cooldown_seconds: float = 300.0
    expert_provider: str = "openai"
    openai_model: str = "gpt-5.6-luna"
    openai_reasoning_effort: str = "low"


@dataclass
class PathConfig:
    """Filesystem locations used by Mary."""

    root: Path = field(default_factory=_resource_root)
    data_root: Path | None = None

    @property
    def data(self) -> Path:
        return self.data_root or _default_data_root(self.root)

    @property
    def workspace(self) -> Path:
        explicit = os.getenv("MARY_WORKSPACE_ROOT", "").strip()
        if explicit:
            return Path(explicit).expanduser().resolve()
        return self.data / "workspace"

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

    governance: RuntimeLimits = field(
        default_factory=RuntimeLimits
    )

    @classmethod
    def from_environment(cls):
        """
        Create configuration using environment variables where available.

        Existing defaults remain intact when variables are not provided.
        """

        config = cls()
        config.governance = RuntimeLimits.from_environment()

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

        conversation_order_value = os.getenv(
            "MARY_LLM_CONVERSATION_ORDER",
            "",
        )
        if conversation_order_value.strip():
            config.llm.conversation_provider_order = [
                item.strip().lower()
                for item in conversation_order_value.split(",")
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