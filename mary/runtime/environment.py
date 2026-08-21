"""MaryV2 host/capability awareness.

The character core must not depend on Windows, Ollama, Qt, or any one cloud
provider. This module exposes a display-safe process-local view of the host
Mary is running on and resolves configured provider policy into an effective
route for this host.

No durable identity or relationship state is stored here.
"""

from __future__ import annotations

from dataclasses import dataclass
import os
import platform
import sys
from typing import Any


@dataclass(frozen=True)
class ProviderCapability:
    name: str
    configured: bool
    available: bool
    model: str

    def to_dict(self) -> dict[str, Any]:
        return {
            "name": self.name,
            "configured": self.configured,
            "available": self.available,
            "model": self.model,
        }


class RuntimeEnvironment:
    """Process-local host and capability resolver for MaryV2."""

    VERSION = "v2-breakthrough-12"

    _TRUE_VALUES = {
        "1",
        "true",
        "yes",
        "on",
    }

    def __init__(
        self,
        *,
        config: Any,
        router: Any,
    ) -> None:
        self.config = config
        self.router = router

    # ============================================================
    # HOST DETECTION
    # ============================================================

    @classmethod
    def _env_true(
        cls,
        name: str,
    ) -> bool:
        """Return True when an environment flag is explicitly enabled."""

        return (
            os.getenv(
                name,
                "",
            )
            .strip()
            .lower()
            in cls._TRUE_VALUES
        )

    def host_type(self) -> str:
        """
        Detect the current execution host.

        Strong explicit environment markers are intentionally evaluated before
        broader ambient markers.

        This matters for nested/simulated development environments. For
        example, a Codespaces unit test running inside Replit may still inherit
        REPL_* variables from the real host. An explicit CODESPACES=true marker
        must therefore win for that simulated environment.
        """

        # --------------------------------------------------------
        # Explicit / strong host signals
        # --------------------------------------------------------

        if self._env_true(
            "CODESPACES"
        ) or os.getenv(
            "CODESPACE_NAME"
        ):
            return "codespaces"

        # --------------------------------------------------------
        # Replit
        # --------------------------------------------------------

        if (
            os.getenv(
                "REPL_ID"
            )
            or os.getenv(
                "REPL_SLUG"
            )
            or os.getenv(
                "REPLIT_DB_URL"
            )
        ):
            return "replit"

        # --------------------------------------------------------
        # Frozen application
        # --------------------------------------------------------

        if getattr(
            sys,
            "frozen",
            False,
        ):
            return "packaged"

        return "local_development"

    # ============================================================
    # PLATFORM
    # ============================================================

    def platform_name(self) -> str:
        """Return a stable display-safe platform identifier."""

        value = (
            platform.system()
            .strip()
            .lower()
        )

        return {
            "darwin": "macos",
            "windows": "windows",
            "linux": "linux",
        }.get(
            value,
            value or "unknown",
        )

    # ============================================================
    # PROVIDER CAPABILITIES
    # ============================================================

    def provider_capability(
        self,
        name: str,
    ) -> ProviderCapability:
        """
        Resolve one provider's configured and available state.

        Cloud adapters generally treat is_available() as configuration/key
        readiness rather than performing a live network call.

        Ollama may additionally perform its local health check, allowing Mary
        to keep Ollama in preferred policy while truthfully removing it from
        the effective route on hosts where the local service is unavailable.
        """

        normalized = (
            str(
                name
            )
            .strip()
            .lower()
        )

        try:
            provider = self.router.get_provider(
                normalized
            )

            model = str(
                provider.model_name()
            )

        except Exception:
            return ProviderCapability(
                name=normalized,
                configured=False,
                available=False,
                model="unavailable",
            )

        try:
            available = bool(
                provider.is_available()
            )

        except Exception:
            available = False

        # Most providers are considered configured when their adapter reports
        # itself available. Ollama is slightly different because it may be
        # intentionally enabled/configured while the local service itself is
        # not reachable on this host.
        configured = available

        if normalized == "ollama":
            configured = (
                os.getenv(
                    "MARY_OLLAMA_ENABLED",
                    "true",
                )
                .strip()
                .lower()
                in self._TRUE_VALUES
            )

        return ProviderCapability(
            name=normalized,
            configured=bool(
                configured
            ),
            available=bool(
                available
            ),
            model=model,
        )

    def provider_snapshot(
        self,
    ) -> dict[str, dict[str, Any]]:
        """Return display-safe capability state for every known provider."""

        names: list[str] = []

        provider_orders = (
            list(
                self.router.conversation_provider_order()
            ),
            list(
                self.router._provider_order(
                    None
                )
            ),
            [
                "openai",
            ],
        )

        for provider_order in provider_orders:
            for name in provider_order:
                normalized = (
                    str(
                        name
                    )
                    .strip()
                    .lower()
                )

                if (
                    normalized
                    and normalized
                    not in names
                ):
                    names.append(
                        normalized
                    )

        return {
            name: self.provider_capability(
                name
            ).to_dict()
            for name in names
        }

    # ============================================================
    # EFFECTIVE ROUTING
    # ============================================================

    def effective_provider_order(
        self,
        *,
        purpose: str | None = None,
    ) -> list[str]:
        """
        Resolve preferred provider policy against this host's capabilities.

        Preferred policy remains stable across hosts.

        Example:

            preferred conversation:
                ollama -> groq -> gemini -> openrouter

            Replit effective conversation:
                groq -> gemini -> openrouter

        Ollama remains part of Mary's policy without becoming a mandatory
        dependency of every runtime.
        """

        normalized_purpose = (
            str(
                purpose or ""
            )
            .strip()
            .lower()
        )

        conversation_purposes = {
            "conversation",
            "character",
            "relational",
            "self",
        }

        if normalized_purpose in conversation_purposes:
            preferred = list(
                self.router.conversation_provider_order()
            )

        else:
            preferred = list(
                self.router._provider_order(
                    None
                )
            )

        snapshot = self.provider_snapshot()

        effective: list[str] = []

        for name in preferred:
            normalized = (
                str(
                    name
                )
                .strip()
                .lower()
            )

            capability = snapshot.get(
                normalized,
                {},
            )

            if bool(
                capability.get(
                    "available"
                )
            ):
                effective.append(
                    normalized
                )

        return effective

    # ============================================================
    # HOST CAPABILITIES
    # ============================================================

    def capabilities(
        self,
    ) -> dict[str, bool]:
        """
        Return broad host capabilities.

        These describe the execution environment, not Mary's identity.
        """

        host = self.host_type()

        desktop_host = (
            host
            in {
                "local_development",
                "packaged",
            }
        )

        platform_value = self.platform_name()

        return {
            "filesystem": True,
            "persistent_local_storage": True,
            "desktop_ui": bool(
                desktop_host
                and platform_value
                in {
                    "windows",
                    "macos",
                    "linux",
                }
            ),
            "native_microphone": bool(
                desktop_host
            ),
            "native_audio": bool(
                desktop_host
            ),
            "avatar": bool(
                desktop_host
            ),
            "web_tools": True,
        }

    # ============================================================
    # SNAPSHOT
    # ============================================================

    def snapshot(
        self,
    ) -> dict[str, Any]:
        """Return Mary's display-safe process-local environment snapshot."""

        conversation_policy = list(
            self.router.conversation_provider_order()
        )

        task_policy = list(
            self.router._provider_order(
                None
            )
        )

        return {
            "connected": True,
            "version": self.VERSION,
            "host_type": self.host_type(),
            "platform": self.platform_name(),
            "runtime_mode": str(
                getattr(
                    self.config.runtime,
                    "environment",
                    "development",
                )
            ),
            "providers": self.provider_snapshot(),
            "conversation_policy": conversation_policy,
            "effective_conversation_route": self.effective_provider_order(
                purpose="conversation"
            ),
            "task_policy": task_policy,
            "effective_task_route": self.effective_provider_order(
                purpose=None
            ),
            "capabilities": self.capabilities(),
        }