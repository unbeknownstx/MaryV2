"""
MaryV2 - Tool Registry

Central registry for Mary's capabilities.

IMPORTANT SECURITY MODEL
------------------------

The registry is an enforcement boundary.

Mary may REQUEST an action, but requesting an action does not grant
permission to execute it.

Potentially dangerous capabilities require explicit creator approval.

Examples:

    - internet access
    - external network communication
    - filesystem writes
    - code execution
    - package installation
    - tool creation/modification
    - configuration changes
    - identity/personality changes
    - permanent knowledge changes
    - autonomous capability changes

The LLM is never trusted to enforce these rules itself.

Python enforces them here.

Creator identity:
    unbe

The creator's real-world name is intentionally not stored here.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from enum import Enum
from typing import Any, Callable
from uuid import uuid4


# ================================================================
# TYPES
# ================================================================


ToolFunction = Callable[..., Any]
ExecutionPolicy = Callable[[str], None]


class PermissionLevel(str, Enum):
    """
    Permission requirements for tools.

    SAFE:
        No explicit approval required.

    APPROVAL_REQUIRED:
        Mary must receive explicit creator approval before execution.

    NEVER_AUTONOMOUS:
        The tool cannot be executed through normal autonomous
        operation. It requires a dedicated, explicitly authorized
        pathway.
    """

    SAFE = "safe"

    APPROVAL_REQUIRED = "approval_required"

    NEVER_AUTONOMOUS = "never_autonomous"


class ToolCategory(str, Enum):
    """
    Standard Mary tool categories.
    """

    GENERAL = "general"

    WEB = "web"

    NETWORK = "network"

    FILESYSTEM = "filesystem"

    CODE = "code"

    SYSTEM = "system"

    KNOWLEDGE = "knowledge"

    LEARNING = "learning"

    DEVELOPMENT = "development"


@dataclass(frozen=True)
class ApprovalToken:
    """
    Represents explicit creator approval for one requested action.

    Tokens are intentionally:

        - unique
        - scoped to one tool
        - scoped to one request
        - non-reusable
        - non-transferable

    Mary cannot manufacture a valid token herself because tokens
    are created by the permission/approval layer.
    """

    token_id: str

    tool_name: str

    request_id: str

    approved_by: str

    reason: str = ""


@dataclass
class ToolResult:
    """
    Standard result returned by a tool execution attempt.
    """

    success: bool

    tool_name: str

    result: Any = None

    error: str | None = None

    metadata: dict[str, Any] = field(
        default_factory=dict
    )

    approval_required: bool = False

    def to_dict(
        self,
    ) -> dict[str, Any]:
        """
        Convert the result into a serializable dictionary.
        """

        return {
            "success": self.success,
            "tool_name": self.tool_name,
            "result": self.result,
            "error": self.error,
            "metadata": dict(
                self.metadata
            ),
            "approval_required": (
                self.approval_required
            ),
        }


@dataclass
class ToolRequest:
    """
    Represents Mary's request to execute a tool.

    A request is NOT permission.

    It is simply a structured request that can be presented to the
    creator for approval.
    """

    request_id: str

    tool_name: str

    arguments: dict[str, Any]

    reason: str

    created_by: str = "mary"

    status: str = "pending"

    approval_token: ApprovalToken | None = None


@dataclass
class ToolDefinition:
    """
    Describes a registered capability.
    """

    name: str

    description: str

    function: ToolFunction

    category: str = "general"

    version: str = "1.0"

    enabled: bool = True

    permission_level: PermissionLevel = (
        PermissionLevel.SAFE
    )

    external_access: bool = False

    mutates_state: bool = False

    creator_sensitive: bool = False

    parameters: dict[str, Any] = field(
        default_factory=dict
    )

    metadata: dict[str, Any] = field(
        default_factory=dict
    )

    execution_count: int = 0

    failure_count: int = 0

    def summary(
        self,
    ) -> dict[str, Any]:
        """
        Return a safe description of the tool.

        The callable implementation itself is never exposed.
        """

        return {
            "name": self.name,
            "description": self.description,
            "category": self.category,
            "version": self.version,
            "enabled": self.enabled,
            "permission_level": (
                self.permission_level.value
            ),
            "external_access": (
                self.external_access
            ),
            "mutates_state": (
                self.mutates_state
            ),
            "creator_sensitive": (
                self.creator_sensitive
            ),
            "parameters": dict(
                self.parameters
            ),
            "metadata": dict(
                self.metadata
            ),
            "execution_count": (
                self.execution_count
            ),
            "failure_count": (
                self.failure_count
            ),
        }


# ================================================================
# TOOL REGISTRY
# ================================================================


class ToolRegistry:
    """
    Central capability registry for Mary.

    Security principle:

        registration != permission

        request != permission

        approval != permanent permission

    Every approval is scoped to a specific request and tool.
    """

    CREATOR = "unbe"

    def __init__(
        self,
    ) -> None:
        self._tools: dict[
            str,
            ToolDefinition,
        ] = {}

        self._requests: dict[
            str,
            ToolRequest,
        ] = {}

        self._used_tokens: set[
            str
        ] = set()
        # Optional process-local execution boundary.  It is permissive until an
        # embedding application explicitly installs a policy.
        self._execution_policy: ExecutionPolicy | None = None

    def set_execution_policy(
        self,
        policy: ExecutionPolicy | None,
    ) -> None:
        """Set the policy called at the tool execution boundary.

        The callback receives ``"tool.execute"`` and may raise
        ``RuntimeError`` to deny an execution attempt.
        """

        self._execution_policy = policy

    # ============================================================
    # REGISTRATION
    # ============================================================

    def register(
        self,
        name: str,
        description: str,
        function: ToolFunction,
        *,
        category: str = "general",
        version: str = "1.0",
        enabled: bool = True,
        permission_level: PermissionLevel | str = (
            PermissionLevel.SAFE
        ),
        external_access: bool = False,
        mutates_state: bool = False,
        creator_sensitive: bool = False,
        parameters: dict[str, Any] | None = None,
        metadata: dict[str, Any] | None = None,
        overwrite: bool = False,
    ) -> ToolDefinition:
        """
        Register a capability.

        Dangerous capabilities are automatically elevated to
        APPROVAL_REQUIRED even if the caller accidentally attempts
        to register them as SAFE.
        """

        normalized_name = self._normalize_name(
            name
        )

        if not normalized_name:
            raise ValueError(
                "Tool name cannot be empty."
            )

        if not callable(
            function
        ):
            raise TypeError(
                "Tool function must be callable."
            )

        if (
            normalized_name in self._tools
            and not overwrite
        ):
            raise ValueError(
                f"Tool already registered: "
                f"{normalized_name}"
            )

        permission = self._normalize_permission(
            permission_level
        )

        # --------------------------------------------------------
        # SECURITY ESCALATION
        # --------------------------------------------------------
        #
        # A tool cannot declare itself safe merely by setting
        # permission_level=SAFE if it performs dangerous actions.
        #

        if (
            external_access
            or mutates_state
            or creator_sensitive
        ):
            if permission == PermissionLevel.SAFE:
                permission = (
                    PermissionLevel.APPROVAL_REQUIRED
                )

        definition = ToolDefinition(
            name=normalized_name,
            description=str(
                description
            ).strip(),
            function=function,
            category=str(
                category
            ).strip().lower()
            or ToolCategory.GENERAL.value,
            version=str(
                version
            ).strip()
            or "1.0",
            enabled=bool(
                enabled
            ),
            permission_level=permission,
            external_access=bool(
                external_access
            ),
            mutates_state=bool(
                mutates_state
            ),
            creator_sensitive=bool(
                creator_sensitive
            ),
            parameters=dict(
                parameters or {}
            ),
            metadata=dict(
                metadata or {}
            ),
        )

        self._tools[
            normalized_name
        ] = definition

        return definition

    def unregister(
        self,
        name: str,
    ) -> bool:
        """
        Remove a registered tool.

        Removing a capability is itself a system modification and
        should normally be performed by the application owner,
        not by Mary's autonomous loop.
        """

        normalized_name = (
            self._normalize_name(
                name
            )
        )

        if (
            normalized_name
            not in self._tools
        ):
            return False

        del self._tools[
            normalized_name
        ]

        return True

    # ============================================================
    # LOOKUP
    # ============================================================

    def get(
        self,
        name: str,
    ) -> ToolDefinition | None:
        """
        Retrieve a tool definition.
        """

        return self._tools.get(
            self._normalize_name(
                name
            )
        )

    def has(
        self,
        name: str,
    ) -> bool:
        """
        Check whether a tool exists.
        """

        return self.get(
            name
        ) is not None

    def all(
        self,
    ) -> list[ToolDefinition]:
        """
        Return all registered tools.
        """

        return list(
            self._tools.values()
        )

    # ============================================================
    # ENABLE / DISABLE
    # ============================================================

    def enable(
        self,
        name: str,
    ) -> bool:
        """
        Enable a registered tool.

        NOTE:
            Enabling a capability does not bypass its permission
            requirement.
        """

        tool = self.get(
            name
        )

        if tool is None:
            return False

        tool.enabled = True

        return True

    def disable(
        self,
        name: str,
    ) -> bool:
        """
        Disable a registered tool.
        """

        tool = self.get(
            name
        )

        if tool is None:
            return False

        tool.enabled = False

        return True

    def is_enabled(
        self,
        name: str,
    ) -> bool:
        """
        Check whether a tool exists and is enabled.
        """

        tool = self.get(
            name
        )

        return (
            tool is not None
            and tool.enabled
        )

    # ============================================================
    # DISCOVERY
    # ============================================================

    def discover(
        self,
        *,
        category: str | None = None,
        enabled_only: bool = True,
        safe_only: bool = False,
    ) -> list[ToolDefinition]:
        """
        Discover available capabilities.

        safe_only=True returns only capabilities that can execute
        without explicit creator approval.
        """

        results: list[
            ToolDefinition
        ] = []

        normalized_category = (
            str(
                category
            ).strip().lower()
            if category
            else None
        )

        for tool in self._tools.values():

            if (
                enabled_only
                and not tool.enabled
            ):
                continue

            if (
                normalized_category
                and tool.category
                != normalized_category
            ):
                continue

            if (
                safe_only
                and tool.permission_level
                != PermissionLevel.SAFE
            ):
                continue

            results.append(
                tool
            )

        return results

    def find(
        self,
        query: str,
    ) -> list[ToolDefinition]:
        """
        Basic lexical capability discovery.

        Discovery does not grant permission.
        """

        query_words = self._words(
            query
        )

        if not query_words:
            return []

        matches: list[
            tuple[
                float,
                ToolDefinition,
            ]
        ] = []

        for tool in self._tools.values():

            if not tool.enabled:
                continue

            searchable = self._words(
                " ".join(
                    [
                        tool.name,
                        tool.description,
                        tool.category,
                    ]
                )
            )

            overlap = (
                query_words
                & searchable
            )

            if not overlap:
                continue

            score = (
                len(overlap)
                / len(query_words)
            )

            matches.append(
                (
                    score,
                    tool,
                )
            )

        matches.sort(
            key=lambda item: item[0],
            reverse=True,
        )

        return [
            item[1]
            for item in matches
        ]

    # ============================================================
    # REQUEST / APPROVAL SYSTEM
    # ============================================================

    def request_execution(
        self,
        name: str,
        arguments: dict[str, Any] | None = None,
        *,
        reason: str = "",
    ) -> ToolRequest:
        """
        Create a tool execution request.

        IMPORTANT:

            This NEVER executes the tool.

        It creates a pending request that can be reviewed by the
        creator.
        """

        tool = self.get(
            name
        )

        normalized_name = (
            self._normalize_name(
                name
            )
        )

        request = ToolRequest(
            request_id=self._new_request_id(),
            tool_name=normalized_name,
            arguments=dict(
                arguments or {}
            ),
            reason=str(
                reason
            ).strip(),
        )

        if tool is None:
            request.status = "rejected"

        elif not tool.enabled:
            request.status = "rejected"

        else:
            request.status = "pending"

        self._requests[
            request.request_id
        ] = request

        return request

    def approve_request(
        self,
        request_id: str,
        *,
        approved_by: str = CREATOR,
        reason: str = "",
    ) -> ApprovalToken | None:
        """
        Approve a pending request.

        This method represents the explicit creator approval
        boundary.

        Mary should never be given authority to call this method
        autonomously.
        """

        request = self._requests.get(
            request_id
        )

        if request is None:
            return None

        if request.status != "pending":
            return None

        if approved_by != self.CREATOR:
            return None

        tool = self.get(
            request.tool_name
        )

        if tool is None:
            request.status = "rejected"
            return None

        token = ApprovalToken(
            token_id=self._new_token_id(),
            tool_name=tool.name,
            request_id=request.request_id,
            approved_by=approved_by,
            reason=(
                str(
                    reason
                ).strip()
                or request.reason
            ),
        )

        request.approval_token = token
        request.status = "approved"

        return token

    def reject_request(
        self,
        request_id: str,
    ) -> bool:
        """
        Reject a pending request.
        """

        request = self._requests.get(
            request_id
        )

        if request is None:
            return False

        if request.status != "pending":
            return False

        request.status = "rejected"

        return True

    def get_request(
        self,
        request_id: str,
    ) -> ToolRequest | None:
        """
        Retrieve a tool request.
        """

        return self._requests.get(
            request_id
        )

    def pending_requests(
        self,
    ) -> list[ToolRequest]:
        """
        Return requests awaiting approval.
        """

        return [
            request
            for request
            in self._requests.values()
            if request.status
            == "pending"
        ]

    # ============================================================
    # EXECUTION
    # ============================================================

    def execute(
        self,
        name: str,
        *args: Any,
        approval_token: ApprovalToken | None = None,
        **kwargs: Any,
    ) -> ToolResult:
        """
        Execute a registered tool.

        SAFE tools can execute directly.

        APPROVAL_REQUIRED tools require a valid, unused,
        request-scoped ApprovalToken.

        NEVER_AUTONOMOUS tools cannot execute through this method.
        """

        tool = self.get(
            name
        )

        if tool is None:
            return ToolResult(
                success=False,
                tool_name=str(
                    name
                ),
                error=(
                    "Tool is not registered."
                ),
            )

        if not tool.enabled:
            return ToolResult(
                success=False,
                tool_name=tool.name,
                error=(
                    "Tool is disabled."
                ),
            )

        try:
            if self._execution_policy is not None:
                self._execution_policy("tool.execute")
        except RuntimeError as exc:
            # Do not call the tool or consume a one-shot approval token when
            # process-local execution has been suspended.
            return ToolResult(
                success=False,
                tool_name=tool.name,
                error=f"Tool execution denied by policy: {exc}",
                metadata={"denied_by_policy": True},
            )

        permission_error = (
            self._check_permission(
                tool,
                approval_token,
            )
        )

        if permission_error is not None:
            return ToolResult(
                success=False,
                tool_name=tool.name,
                error=permission_error,
                approval_required=(
                    tool.permission_level
                    == PermissionLevel.APPROVAL_REQUIRED
                ),
            )

        try:
            result = tool.function(
                *args,
                **kwargs,
            )

            tool.execution_count += 1

            if approval_token is not None:
                self._consume_token(
                    approval_token
                )

            if isinstance(
                result,
                ToolResult,
            ):
                return result

            return ToolResult(
                success=True,
                tool_name=tool.name,
                result=result,
            )

        except Exception as exc:
            tool.execution_count += 1
            tool.failure_count += 1

            if approval_token is not None:
                self._consume_token(
                    approval_token
                )

            return ToolResult(
                success=False,
                tool_name=tool.name,
                error=str(
                    exc
                ),
                metadata={
                    "exception_type": (
                        type(exc).__name__
                    ),
                },
            )

    def execute_approved(
        self,
        request_id: str,
    ) -> ToolResult:
        """
        Execute a previously approved request.

        The approval token is retrieved from the request and is
        consumed after execution.

        This is the preferred path for approved tool operations.
        """

        request = self.get_request(
            request_id
        )

        if request is None:
            return ToolResult(
                success=False,
                tool_name="unknown",
                error=(
                    "Execution request "
                    "does not exist."
                ),
            )

        if request.status != "approved":
            return ToolResult(
                success=False,
                tool_name=request.tool_name,
                error=(
                    "Request has not received "
                    "creator approval."
                ),
                approval_required=True,
            )

        token = request.approval_token

        if token is None:
            return ToolResult(
                success=False,
                tool_name=request.tool_name,
                error=(
                    "Approved request has "
                    "no approval token."
                ),
                approval_required=True,
            )

        result = self.execute(
            request.tool_name,
            approval_token=token,
            **request.arguments,
        )

        request.status = (
            "executed"
            if result.success
            else "failed"
        )

        return result

    # ============================================================
    # VALIDATION
    # ============================================================

    def validate(
        self,
        name: str,
        arguments: dict[str, Any] | None = None,
    ) -> tuple[
        bool,
        str | None,
    ]:
        """
        Perform basic parameter validation.
        """

        tool = self.get(
            name
        )

        if tool is None:
            return (
                False,
                "Tool is not registered.",
            )

        arguments = dict(
            arguments or {}
        )

        schema = tool.parameters

        if not schema:
            return (
                True,
                None,
            )

        for parameter_name, definition in (
            schema.items()
        ):
            if not isinstance(
                definition,
                dict,
            ):
                continue

            required = bool(
                definition.get(
                    "required",
                    False,
                )
            )

            if (
                required
                and parameter_name
                not in arguments
            ):
                return (
                    False,
                    (
                        f"Missing required "
                        f"parameter: "
                        f"{parameter_name}"
                    ),
                )

            if (
                parameter_name
                not in arguments
            ):
                continue

            expected_type = definition.get(
                "type"
            )

            if (
                expected_type is None
                or expected_type == "any"
            ):
                continue

            if not self._matches_type(
                arguments[
                    parameter_name
                ],
                expected_type,
            ):
                return (
                    False,
                    (
                        f"Invalid type for "
                        f"parameter "
                        f"'{parameter_name}'. "
                        f"Expected "
                        f"{expected_type}."
                    ),
                )

        return (
            True,
            None,
        )

    def execute_validated(
        self,
        name: str,
        arguments: dict[str, Any] | None = None,
        *,
        approval_token: ApprovalToken | None = None,
    ) -> ToolResult:
        """
        Validate arguments and then execute.

        Permission checks still apply.
        """

        arguments = dict(
            arguments or {}
        )

        valid, error = self.validate(
            name,
            arguments,
        )

        if not valid:
            return ToolResult(
                success=False,
                tool_name=str(
                    name
                ),
                error=error,
            )

        return self.execute(
            name,
            approval_token=approval_token,
            **arguments,
        )

    # ============================================================
    # METADATA
    # ============================================================

    def summaries(
        self,
        *,
        enabled_only: bool = True,
    ) -> list[dict[str, Any]]:
        """
        Return serializable descriptions of tools.
        """

        return [
            tool.summary()
            for tool in self.discover(
                enabled_only=enabled_only
            )
        ]

    def categories(
        self,
    ) -> list[str]:
        """
        Return registered categories.
        """

        return sorted(
            {
                tool.category
                for tool in self._tools.values()
            }
        )

    def statistics(
        self,
    ) -> dict[str, Any]:
        """
        Return registry statistics.
        """

        tools = list(
            self._tools.values()
        )

        return {
            "total": len(
                tools
            ),
            "enabled": sum(
                1
                for tool in tools
                if tool.enabled
            ),
            "disabled": sum(
                1
                for tool in tools
                if not tool.enabled
            ),
            "safe": sum(
                1
                for tool in tools
                if tool.permission_level
                == PermissionLevel.SAFE
            ),
            "approval_required": sum(
                1
                for tool in tools
                if tool.permission_level
                == PermissionLevel.APPROVAL_REQUIRED
            ),
            "never_autonomous": sum(
                1
                for tool in tools
                if tool.permission_level
                == PermissionLevel.NEVER_AUTONOMOUS
            ),
            "pending_requests": len(
                self.pending_requests()
            ),
            "executions": sum(
                tool.execution_count
                for tool in tools
            ),
            "failures": sum(
                tool.failure_count
                for tool in tools
            ),
        }

    # ============================================================
    # SECURITY
    # ============================================================

    def _check_permission(
        self,
        tool: ToolDefinition,
        token: ApprovalToken | None,
    ) -> str | None:
        """
        Enforce the permission boundary.
        """

        if (
            tool.permission_level
            == PermissionLevel.NEVER_AUTONOMOUS
        ):
            return (
                "This capability cannot be "
                "executed autonomously."
            )

        if (
            tool.permission_level
            == PermissionLevel.SAFE
        ):
            return None

        if token is None:
            return (
                "Explicit creator approval "
                "is required before this "
                "tool can execute."
            )

        if token.token_id in self._used_tokens:
            return (
                "Approval token has already "
                "been consumed."
            )

        if token.tool_name != tool.name:
            return (
                "Approval token is not valid "
                "for this tool."
            )

        request = self._requests.get(
            token.request_id
        )

        if request is None:
            return (
                "Approval request does not "
                "exist."
            )

        if request.status != "approved":
            return (
                "Approval request is not "
                "currently approved."
            )

        if request.approval_token != token:
            return (
                "Approval token does not "
                "match the approved request."
            )

        if token.approved_by != self.CREATOR:
            return (
                "Approval was not granted "
                "by the creator."
            )

        return None

    def _consume_token(
        self,
        token: ApprovalToken,
    ) -> None:
        """
        Permanently consume an approval token.
        """

        self._used_tokens.add(
            token.token_id
        )

    # ============================================================
    # HELPERS
    # ============================================================

    @staticmethod
    def _normalize_name(
        name: str,
    ) -> str:
        """
        Normalize tool names.
        """

        return (
            str(
                name
            )
            .strip()
            .lower()
            .replace(
                " ",
                "_",
            )
        )

    @staticmethod
    def _normalize_permission(
        permission: PermissionLevel | str,
    ) -> PermissionLevel:
        """
        Normalize a permission level.
        """

        if isinstance(
            permission,
            PermissionLevel,
        ):
            return permission

        try:
            return PermissionLevel(
                str(
                    permission
                ).strip().lower()
            )
        except ValueError:
            raise ValueError(
                "Invalid permission level: "
                f"{permission}"
            )

    @staticmethod
    def _words(
        text: str,
    ) -> set[str]:
        """
        Convert text into searchable words.
        """

        punctuation = (
            ".,!?;:\"'()[]{}"
        )

        return {
            word.strip(
                punctuation
            ).lower()
            for word in str(
                text
            ).split()
            if word.strip(
                punctuation
            )
        }

    @staticmethod
    def _matches_type(
        value: Any,
        expected_type: str,
    ) -> bool:
        """
        Validate a basic parameter type.
        """

        expected_type = (
            str(
                expected_type
            ).strip().lower()
        )

        if expected_type == "string":
            return isinstance(
                value,
                str,
            )

        if expected_type == "integer":
            return (
                isinstance(
                    value,
                    int,
                )
                and not isinstance(
                    value,
                    bool,
                )
            )

        if expected_type == "number":
            return (
                isinstance(
                    value,
                    (int, float),
                )
                and not isinstance(
                    value,
                    bool,
                )
            )

        if expected_type == "boolean":
            return isinstance(
                value,
                bool,
            )

        if expected_type == "object":
            return isinstance(
                value,
                dict,
            )

        if expected_type == "array":
            return isinstance(
                value,
                (list, tuple),
            )

        return True

    @staticmethod
    def _new_request_id() -> str:
        """
        Generate a unique execution request ID.
        """

        return (
            "request_"
            + uuid4().hex
        )

    @staticmethod
    def _new_token_id() -> str:
        """
        Generate a unique approval token ID.
        """

        return (
            "approval_"
            + uuid4().hex
        )


# ================================================================
# DEFAULT REGISTRY
# ================================================================


_default_registry: ToolRegistry | None = None


def get_default_registry() -> ToolRegistry:
    """
    Return Mary's process-wide default registry.

    Tools are intentionally NOT automatically registered.

    Capability registration must happen explicitly during
    application startup.
    """

    global _default_registry

    if _default_registry is None:
        _default_registry = ToolRegistry()

    return _default_registry