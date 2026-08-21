"""Display-safe runtime introspection for MaryV2.

Natural questions about Mary's current host, providers, routes, and portability
must be answered from process-local runtime state rather than from a language
model or the web.  This module keeps those answers concise and question-shaped.

It owns no durable Mary state and performs no network calls itself.
"""

from __future__ import annotations

from dataclasses import dataclass
from typing import Any

from mary.cognition.natural_input import normalize_for_matching




def is_personal_runtime_reaction(query: str) -> bool:
    """Return True when runtime context is part of a personal Mary turn.

    These turns mention the current host/device, but the user is primarily
    asking for Mary's reaction or perspective rather than requesting a
    diagnostic/runtime fact dump.  They should remain model-backed Mary
    conversation while receiving a small grounded runtime context.
    """

    text = normalize_for_matching(str(query or ""))
    tokens = set(text.split())

    host_markers = (
        "macbook", "mac", "macos", "replit", "codespaces", "pc",
        "computer", "laptop", "phone", "iphone", "ipad", "windows",
        "linux", "different machine", "different device", "running on",
        "running from", "working on you from", "working on u from",
    )
    reaction_markers = (
        "what do you think", "what do u think", "how do you feel",
        "how do u feel", "what does that feel like", "isnt that cool",
        "isn't that cool", "kinda cool", "kind of cool", "pretty cool",
        "first time", "we are running", "were running", "we're running",
        "working on you from", "working on u from",
    )

    has_host = any(marker in text for marker in host_markers) or bool(
        tokens.intersection({"macbook", "replit", "codespaces", "pc", "laptop", "phone", "iphone", "ipad", "macos"})
    )
    has_reaction = any(marker in text for marker in reaction_markers)

    # Pure runtime questions such as "where are you running?" or
    # "what models can you use?" intentionally remain deterministic.
    pure_runtime_markers = (
        "where are you running", "where are u running",
        "what models can", "which models can", "what providers can",
        "which providers can", "what environment", "what host",
        "can you use ollama", "can u use ollama",
        "does anything about how you work change",
        "does anything about how u work change",
    )
    if any(marker in text for marker in pure_runtime_markers):
        return False

    return bool(has_host and has_reaction)


@dataclass(frozen=True)
class RuntimeQuery:
    kind: str
    provider: str | None = None


class RuntimeIntrospection:
    """Classify and render deterministic runtime/environment answers."""

    VERSION = "v2-breakthrough-12.3"

    _PROVIDERS = ("ollama", "groq", "gemini", "openrouter", "openai")

    def classify(self, query: str) -> RuntimeQuery:
        text = normalize_for_matching(str(query or ""))
        tokens = set(text.split())

        for provider in self._PROVIDERS:
            if provider in text.replace("open router", "openrouter").replace("open ai", "openai"):
                if any(word in tokens for word in {"available", "using", "use", "access", "reachable", "ready"}) or "can" in tokens:
                    return RuntimeQuery("provider_specific", provider)

        if any(phrase in text for phrase in (
            "what models can", "which models can", "what model can",
            "what providers can", "which providers can", "providers are available",
            "models are available", "models can you ise", "models can u ise",
        )):
            return RuntimeQuery("providers")

        if any(phrase in text for phrase in (
            "what host", "which host", "what environment", "which environment",
            "where are you running", "where are u running", "are you running on replit",
            "are you running in replit", "are you on replit", "are u on replit",
            "what are you running on", "what platform",
        )):
            return RuntimeQuery("host")

        if any(phrase in text for phrase in (
            "not on my pc", "not at my pc", "not on the pc", "not at the pc",
            "different computer", "different laptop", "different device",
            "because were on replit", "because we're on replit",
            "how you work change", "how u work change", "does anything change",
            "what changes when", "work differently",
        )):
            return RuntimeQuery("portability")

        if any(phrase in text for phrase in (
            "last answer", "last response", "generated that answer",
            "generated that response", "what generated",
        )):
            return RuntimeQuery("last_generation")

        return RuntimeQuery("architecture")

    def render(
        self,
        *,
        query: str,
        environment: dict[str, Any],
        routing_strategy: str,
        configured_task_route: list[str],
        configured_conversation_route: list[str],
        session_override: dict[str, Any] | None = None,
        last_generation: dict[str, Any] | None = None,
    ) -> str:
        request = self.classify(query)
        providers = dict(environment.get("providers", {}) or {})
        effective_conversation = list(environment.get("effective_conversation_route", []) or [])
        effective_task = list(environment.get("effective_task_route", []) or [])
        host = str(environment.get("host_type", "unknown"))
        platform_name = str(environment.get("platform", "unknown"))

        if request.kind == "providers":
            return self._providers_answer(
                providers=providers,
                host=host,
                platform_name=platform_name,
                effective_conversation=effective_conversation,
                effective_task=effective_task,
            )

        if request.kind == "provider_specific" and request.provider:
            return self._provider_answer(
                provider=request.provider,
                providers=providers,
                host=host,
                effective_conversation=effective_conversation,
                effective_task=effective_task,
            )

        if request.kind == "host":
            capabilities = dict(environment.get("capabilities", {}) or {})
            available = self._available_names(providers)
            return (
                f"I'm running on {host} / {platform_name} in this process. "
                f"Available generation providers here are {self._natural_list(available) if available else 'none currently detected'}. "
                f"Desktop UI is {'available' if capabilities.get('desktop_ui') else 'not available'} on this host."
            )

        if request.kind == "portability":
            unavailable = self._unavailable_configured_names(providers)
            unavailable_text = self._natural_list(unavailable) if unavailable else "none of my configured providers"
            return (
                f"My core MaryV2 architecture does not change because I'm on {host} / {platform_name}, but this host changes which capabilities I can actually use. "
                f"Here my effective conversation route is {self._route(effective_conversation)}, and my effective task/general route is {self._route(effective_task)}. "
                f"Unavailable on this host: {unavailable_text}. I skip unavailable capabilities rather than treating them as part of my identity."
            )

        if request.kind == "last_generation":
            previous = dict(last_generation or {})
            if not previous:
                return "I don't have a previous successful model-backed turn recorded in this process yet."
            provider = str(previous.get("provider") or "unknown")
            model = str(previous.get("model") or "unknown")
            finish_reason = str(previous.get("finish_reason") or "unknown")
            return (
                f"My most recent successful model-backed turn used {provider} with {model} "
                f"(finish reason: {finish_reason}). No language model is being asked to guess that; "
                "it comes from my process-local generation metadata."
            )

        # Full architecture response is intentionally reserved for genuinely
        # broad architecture questions rather than every provider/host query.
        override = dict(session_override or {})
        parts = [
            (
                "I'm MaryV2. My identity, memory, personality, relationship model, cognition, agency, tools, expression, and other connected systems run in my Python architecture. "
                "Language models are routed generation engines; they are not my identity."
            ),
            f"This process is running on {host} / {platform_name}.",
            f"My general/task routing strategy is {routing_strategy}: {self._route(configured_task_route)}.",
            f"My preferred personal conversation route is {self._route(configured_conversation_route)}, while the effective route on this host is {self._route(effective_conversation)}.",
            f"My effective task/general route on this host is {self._route(effective_task)}.",
        ]
        if override.get("route") == "private":
            parts.append("A process-local private/Ollama override is active.")
        elif override.get("provider"):
            parts.append(f"A process-local provider override is active: {override.get('provider')}.")
        return " ".join(parts)

    @staticmethod
    def _route(names: list[str]) -> str:
        return " -> ".join(str(name) for name in names if str(name).strip()) or "no currently available provider"

    @staticmethod
    def _available_names(providers: dict[str, Any]) -> list[str]:
        return [name for name, data in providers.items() if bool(dict(data or {}).get("available"))]

    @staticmethod
    def _unavailable_configured_names(providers: dict[str, Any]) -> list[str]:
        return [
            name
            for name, data in providers.items()
            if bool(dict(data or {}).get("configured")) and not bool(dict(data or {}).get("available"))
        ]

    @staticmethod
    def _natural_list(items: list[str]) -> str:
        clean = [str(item) for item in items if str(item).strip()]
        if not clean:
            return ""
        if len(clean) == 1:
            return clean[0]
        if len(clean) == 2:
            return f"{clean[0]} and {clean[1]}"
        return ", ".join(clean[:-1]) + f", and {clean[-1]}"

    def _providers_answer(
        self,
        *,
        providers: dict[str, Any],
        host: str,
        platform_name: str,
        effective_conversation: list[str],
        effective_task: list[str],
    ) -> str:
        available = self._available_names(providers)
        unavailable = self._unavailable_configured_names(providers)
        parts = [
            f"Right now on {host} / {platform_name}, I can use {self._natural_list(available) if available else 'no generation provider currently detected'}.",
            f"My effective conversation route is {self._route(effective_conversation)}.",
            f"My effective task/general route is {self._route(effective_task)}.",
        ]
        if unavailable:
            if "ollama" in unavailable:
                parts.append("Ollama is not reachable on this host right now, so I skip it.")
                remaining = [name for name in unavailable if name != "ollama"]
                if remaining:
                    parts.append(f"Also configured but unavailable here: {self._natural_list(remaining)}.")
            else:
                parts.append(f"Configured but unavailable here: {self._natural_list(unavailable)}.")
        openai = dict(providers.get("openai", {}) or {})
        if openai.get("available"):
            parts.append("OpenAI is available only as an explicitly authorized one-task expert route.")
        return " ".join(parts)

    def _provider_answer(
        self,
        *,
        provider: str,
        providers: dict[str, Any],
        host: str,
        effective_conversation: list[str],
        effective_task: list[str],
    ) -> str:
        data = dict(providers.get(provider, {}) or {})
        if not data:
            return f"{provider} is not present in my current provider snapshot."
        model = str(data.get("model") or "unknown")
        if data.get("available"):
            if provider == "openai":
                return f"OpenAI is available on this host with {model}, but I only use it for an explicitly authorized one-task expert consultation."
            roles: list[str] = []
            if provider in effective_conversation:
                roles.append("conversation")
            if provider in effective_task:
                roles.append("task/general")
            role_text = self._natural_list(roles) if roles else "configured work"
            return f"Yes. {provider} is available on {host} with {model} and can currently participate in my {role_text} routing."
        if data.get("configured"):
            return f"{provider} is configured with {model}, but it is not reachable/available on this host right now, so I skip it."
        return f"{provider} is not configured as an available provider in this process right now."
