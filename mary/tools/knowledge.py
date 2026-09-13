"""ToolRegistry bridge for Mary's public KnowledgeGateway."""
from __future__ import annotations

from typing import Any

from mary.knowledge.gateway import KnowledgeGateway
from .registry import PermissionLevel, ToolRegistry


class KnowledgeToolClient:
    def __init__(self, gateway: KnowledgeGateway | None = None) -> None:
        self.gateway = gateway or KnowledgeGateway()

    def search(self, query: str, *, categories: list[str] | None = None, limit: int = 4) -> list[dict[str, Any]]:
        value = " ".join(str(query or "").split()).strip()
        if not value:
            raise ValueError("Knowledge query cannot be empty.")
        clean_categories = [str(item).strip().lower() for item in (categories or []) if str(item).strip()]
        return self.gateway.search(
            value,
            categories=clean_categories or None,
            limit_per_source=max(1, min(5, int(limit))),
        )

    def status(self) -> dict[str, Any]:
        return self.gateway.status()


def register_knowledge_tools(registry: ToolRegistry, *, gateway: KnowledgeGateway | None = None) -> KnowledgeToolClient:
    client = KnowledgeToolClient(gateway)
    registry.register(
        name="knowledge_search",
        description="Search bounded public encyclopedic or academic evidence sources.",
        function=client.search,
        category="knowledge",
        version="13.20",
        permission_level=PermissionLevel.APPROVAL_REQUIRED,
        external_access=True,
        mutates_state=False,
        creator_sensitive=False,
        parameters={
            "query": {"type": "string", "required": True},
            "categories": {"type": "array", "required": False},
            "limit": {"type": "integer", "required": False},
        },
        metadata={
            "operation": "network_search",
            "internet": True,
            "read_only": True,
            "authority": "external_evidence_only",
        },
    )
    return client
