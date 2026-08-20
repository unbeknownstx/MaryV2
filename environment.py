"""MaryV2 host/capability awareness.

The character core must not depend on Windows, Ollama, Qt, or any one cloud
provider.  This module exposes a display-safe process-local view of the host
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

    def __init__(self, *, config: Any, router: Any) -> None:
        self.config = config
        self.router = router

    def host_type(self) -> str:
        if os.getenv("REPL_ID") or os.getenv("REPL_SLUG") or os.getenv("REPLIT_DB_URL"):
            return "replit"
        if os.getenv("CODESPACES", "").strip().lower() == "true" or os.getenv("CODESPACE_NAME"):
            return "codespaces"
        if getattr(sys, "frozen", False):
            return "packaged"
        return "local_development"

    def platform_name(self) -> str:
        value = platform.system().strip().lower()
        return {
            "darwin": "macos",
            "windows": "windows",
            "linux": "linux",
        }.get(value, value or "unknown")

    def provider_capability(self, name: str) -> ProviderCapability:
        normalized = str(name).strip().lower()
        try:
            provider = self.router.get_provider(normalized)
            model = str(provider.model_name())
        except Exception:
            return ProviderCapability(normalized, False, False, "unavailable")

        # For cloud adapters is_available is intentionally configuration/key
        # availability rather than a network call. Ollama additionally performs
        # its short localhost health check, so another host can truthfully omit
        # it from the effective route.
        try:
            available = bool(provider.is_available())
        except Exception:
            available = False

        configured = available
        if normalized == "ollama":
            enabled = os.getenv("MARY_OLLAMA_ENABLED", "true").strip().lower() in {
                "1", "true", "yes", "on"
            }
            configured = bool(enabled)

        return ProviderCapability(normalized, configured, available, model)

    def provider_snapshot(self) -> dict[str, dict[str, Any]]:
        names: list[str] = []
        for name in (
            *list(self.router.conversation_provider_order()),
            *list(self.router._provider_order(None)),
            "openai",
        ):
            normalized = str(name).strip().lower()
            if normalized and normalized not in names:
                names.append(normalized)
        return {name: self.provider_capability(name).to_dict() for name in names}

    def effective_provider_order(self, *, purpose: str | None = None) -> list[str]:
        preferred = (
            list(self.router.conversation_provider_order())
            if str(purpose or "").lower().strip() in {"conversation", "character", "relational", "self"}
            else list(self.router._provider_order(None))
        )
        snapshot = self.provider_snapshot()
        return [
            name for name in preferred
            if bool(snapshot.get(str(name).lower(), {}).get("available"))
        ]

    def capabilities(self) -> dict[str, bool]:
        host = self.host_type()
        desktop_host = host in {"local_development", "packaged"}
        return {
            "filesystem": True,
            "persistent_local_storage": True,
            "desktop_ui": bool(desktop_host and self.platform_name() in {"windows", "macos", "linux"}),
            "native_microphone": bool(desktop_host),
            "native_audio": bool(desktop_host),
            "avatar": bool(desktop_host),
            "web_tools": True,
        }

    def snapshot(self) -> dict[str, Any]:
        conversation_policy = list(self.router.conversation_provider_order())
        task_policy = list(self.router._provider_order(None))
        return {
            "connected": True,
            "version": self.VERSION,
            "host_type": self.host_type(),
            "platform": self.platform_name(),
            "runtime_mode": str(getattr(self.config.runtime, "environment", "development")),
            "providers": self.provider_snapshot(),
            "conversation_policy": conversation_policy,
            "effective_conversation_route": self.effective_provider_order(purpose="conversation"),
            "task_policy": task_policy,
            "effective_task_route": self.effective_provider_order(purpose=None),
            "capabilities": self.capabilities(),
        }
