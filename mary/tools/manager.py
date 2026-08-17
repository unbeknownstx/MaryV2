"""
MaryV2 - Tool Manager

Application-facing coordinator for Mary's controlled capabilities.

The ToolManager does not weaken ToolRegistry. It constructs the registry,
registers the existing capability clients, and provides explicit host-level
helpers for creator-authorized requests.

Security rules:

- registration is not permission
- Mary cannot grant herself approval
- external access remains approval-gated by ToolRegistry
- mutating filesystem/code operations remain approval-gated
- explicit creator requests may be approved by the application coordinator
  only for that exact request
- approval tokens remain one-time and request-scoped
"""

from __future__ import annotations

from pathlib import Path
from typing import Any

from .code import CodeClient, register_code_tools
from .filesystem import FilesystemClient, register_filesystem_tools
from .registry import (
    ApprovalToken,
    ToolRegistry,
    ToolRequest,
    ToolResult,
)
from .web import WebClient, WebConfig, register_web_tools


class ToolManager:
    """Coordinate Mary's registered capabilities without bypassing policy."""

    def __init__(
        self,
        *,
        workspace_root: str | Path,
        registry: ToolRegistry | None = None,
        web_config: WebConfig | None = None,
    ) -> None:
        self.registry = (
            registry
            if registry is not None
            else ToolRegistry()
        )

        self.workspace_root = Path(
            workspace_root
        ).resolve()

        self.filesystem: FilesystemClient = (
            register_filesystem_tools(
                self.registry,
                workspace_roots=[
                    self.workspace_root
                ],
            )
        )

        self.code: CodeClient = (
            register_code_tools(
                self.registry,
                filesystem=self.filesystem,
            )
        )

        self.web: WebClient = (
            register_web_tools(
                self.registry,
                config=web_config,
            )
        )

    # ============================================================
    # REQUESTS
    # ============================================================

    def request(
        self,
        tool_name: str,
        arguments: dict[str, Any] | None = None,
        *,
        reason: str = "",
    ) -> ToolRequest:
        """Create a permission request without executing anything."""

        return self.registry.request_execution(
            tool_name,
            arguments=arguments,
            reason=reason,
        )

    def pending_requests(
        self,
    ) -> list[ToolRequest]:
        return self.registry.pending_requests()

    # ============================================================
    # EXPLICIT CREATOR APPROVAL
    # ============================================================

    def approve(
        self,
        request_id: str,
        *,
        reason: str = "",
    ) -> ApprovalToken | None:
        """
        Record creator approval for one existing request.

        This method is for the application/creator boundary. It must not be
        exposed as an autonomous cognition capability.
        """

        return self.registry.approve_request(
            request_id,
            approved_by=ToolRegistry.CREATOR,
            reason=reason,
        )

    def reject(
        self,
        request_id: str,
    ) -> bool:
        return self.registry.reject_request(
            request_id
        )

    def execute_approved(
        self,
        request_id: str,
    ) -> ToolResult:
        """Execute one previously approved request."""

        return self.registry.execute_approved(
            request_id
        )

    def execute_explicit_creator_request(
        self,
        tool_name: str,
        arguments: dict[str, Any] | None = None,
        *,
        reason: str,
    ) -> tuple[ToolRequest, ToolResult]:
        """
        Execute a tool when the creator explicitly requested that exact action.

        The helper still goes through the complete registry flow:

            request -> creator approval token -> execute_approved

        It does not create permanent permission and cannot be reused for a
        different request.
        """

        request = self.request(
            tool_name,
            arguments,
            reason=reason,
        )

        if request.status != "pending":
            return (
                request,
                ToolResult(
                    success=False,
                    tool_name=tool_name,
                    error=(
                        "Tool request could not be created "
                        "or the tool is unavailable."
                    ),
                ),
            )

        token = self.approve(
            request.request_id,
            reason=reason,
        )

        if token is None:
            return (
                request,
                ToolResult(
                    success=False,
                    tool_name=tool_name,
                    error=(
                        "Creator approval could not be recorded."
                    ),
                    approval_required=True,
                ),
            )

        return (
            request,
            self.execute_approved(
                request.request_id
            ),
        )

    # ============================================================
    # STATUS
    # ============================================================

    def status(
        self,
    ) -> dict[str, Any]:
        """Return non-secret tool-system status."""

        return {
            "registered": len(
                self.registry.all()
            ),
            "pending": len(
                self.registry.pending_requests()
            ),
            "web_search_configured": bool(
                getattr(
                    self.web.search_provider,
                    "configured",
                    False,
                )
            ),
            "workspace_root": str(
                self.workspace_root
            ),
        }