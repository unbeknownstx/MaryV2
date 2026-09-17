"""Managed fallback routing for Mary's existing web-evidence capability.

Concrete search backends live in :mod:`mary.tools.web`.  This module owns only
multi-backend fallback policy so there is one implementation of each retrieval
provider and one ToolRegistry boundary around the resulting ``web_search``.
"""

from __future__ import annotations

from dataclasses import dataclass
import os
from typing import Any, Iterable

from .web import (
    BraveSearchProvider,
    SearchResult,
    SearXNGSearchProvider,
    TavilySearchProvider,
)


@dataclass(frozen=True)
class SearchBackendFailure:
    """Display-safe record of one failed fallback attempt."""

    backend: str
    error_type: str


class FallbackSearchProvider:
    """Try configured read-only search providers in a deterministic order."""

    def __init__(
        self,
        providers: Iterable[Any],
        *,
        name: str = "local_first",
    ) -> None:
        self.providers = tuple(providers)
        self.name = str(name or "fallback")
        self.last_failures: tuple[SearchBackendFailure, ...] = ()
        self.last_backend: str | None = None

    @property
    def configured(self) -> bool:
        return any(
            bool(getattr(provider, "configured", False))
            for provider in self.providers
        )

    def search(
        self,
        query: str,
        *,
        limit: int = 10,
        user_agent: str = "MaryV2/0.1",
    ) -> list[SearchResult]:
        failures: list[SearchBackendFailure] = []
        configured = [
            provider
            for provider in self.providers
            if bool(getattr(provider, "configured", False))
        ]

        if not configured:
            raise RuntimeError(
                "No search backend in the local-first chain is configured. "
                "Set MARY_SEARXNG_URL, TAVILY_API_KEY, or BRAVE_API_KEY."
            )

        for provider in configured:
            backend = self._backend_name(provider)
            try:
                results = provider.search(
                    query,
                    limit=limit,
                    user_agent=user_agent,
                )
            except Exception as exc:
                failures.append(
                    SearchBackendFailure(
                        backend=backend,
                        error_type=type(exc).__name__,
                    )
                )
                continue

            normalized = list(results or [])[: max(1, min(int(limit), 20))]
            if not normalized:
                failures.append(
                    SearchBackendFailure(
                        backend=backend,
                        error_type="empty_results",
                    )
                )
                continue

            self.last_backend = backend
            self.last_failures = tuple(failures)
            for item in normalized:
                if isinstance(getattr(item, "metadata", None), dict):
                    item.metadata.setdefault("search_route", self.name)
                    item.metadata.setdefault("selected_backend", backend)
            return normalized

        self.last_backend = None
        self.last_failures = tuple(failures)
        summary = ", ".join(
            f"{failure.backend}:{failure.error_type}"
            for failure in failures
        ) or "no usable result"
        raise RuntimeError(
            "All configured search backends failed: " + summary
        )

    @staticmethod
    def _backend_name(provider: Any) -> str:
        if isinstance(provider, SearXNGSearchProvider):
            return "searxng"
        if isinstance(provider, TavilySearchProvider):
            return "tavily"
        if isinstance(provider, BraveSearchProvider):
            return "brave"
        return type(provider).__name__


def build_managed_search_provider(
    configured_name: str | None,
    *,
    timeout: float = 10.0,
) -> Any | None:
    """Resolve Mary-only multi-provider search modes.

    Concrete single-provider selection belongs to
    :func:`mary.tools.web.create_search_provider`.  Returning ``None`` for
    ``tavily``, ``brave`` and ``searxng`` lets WebClient construct those native
    providers directly.  Only ``local_first`` / ``auto`` is composed here.
    """

    requested = (
        os.getenv("MARY_SEARCH_PROVIDER")
        or configured_name
        or "tavily"
    )
    requested = str(requested).strip().lower()

    if requested in {"local_first", "auto"}:
        return FallbackSearchProvider(
            (
                SearXNGSearchProvider(timeout=timeout),
                TavilySearchProvider(timeout=timeout),
                BraveSearchProvider(timeout=timeout),
            ),
            name="local_first",
        )

    return None
