"""
MaryV2 LLM Interface

Defines the contract that every language-model provider must implement.

The rest of Mary should depend on this interface rather than directly
depending on Groq, OpenAI, or any future provider.
"""

from abc import ABC, abstractmethod
from dataclasses import dataclass, field
from enum import Enum
from typing import Any
from uuid import uuid4


_REDACTION_RECEIPT_TOKEN = object()


class RedactionReceipt:
    """Opaque proof that a trusted host redactor produced exact outbound text."""

    __slots__ = ("_contents", "provenance")

    def __init__(
        self,
        contents: tuple[str, ...],
        provenance: str,
        *,
        _token: object,
    ) -> None:
        if _token is not _REDACTION_RECEIPT_TOKEN:
            raise TypeError("RedactionReceipt is created only by the trusted boundary.")
        self._contents = tuple(str(item) for item in contents)
        self.provenance = str(provenance)[:96]

    def matches_messages(self, messages: tuple["LLMMessage", ...]) -> bool:
        outbound = tuple(
            str(message.content)
            for message in messages
            if str(message.role).strip().lower() not in {"system", "developer"}
        )
        return outbound == self._contents

    def matches_text(self, text: str) -> bool:
        return self._contents == (str(text),)


def _create_message_redaction_receipt(
    messages: tuple["LLMMessage", ...],
    *,
    provenance: str,
) -> RedactionReceipt:
    contents = tuple(
        str(message.content)
        for message in messages
        if str(message.role).strip().lower() not in {"system", "developer"}
    )
    return RedactionReceipt(
        contents,
        provenance,
        _token=_REDACTION_RECEIPT_TOKEN,
    )


def _create_text_redaction_receipt(
    text: str,
    *,
    provenance: str,
) -> RedactionReceipt:
    return RedactionReceipt(
        (str(text),),
        provenance,
        _token=_REDACTION_RECEIPT_TOKEN,
    )


class GenerationOperation(str, Enum):
    """Bounded text operations that may be delegated to an LLM provider."""

    CONVERSATION = "conversation"
    TASK_GENERATION = "task_generation"
    EXPERT_REASONING = "expert_reasoning"
    RESEARCH_SYNTHESIS = "research_synthesis"
    TOOL_PLANNING = "tool_planning"


class GenerationPrivacy(str, Enum):
    """Where request content is allowed to be processed."""

    CLOUD_OK = "cloud_ok"
    REDACT_FIRST = "redact_first"
    LOCAL_ONLY = "local_only"


class GenerationCost(str, Enum):
    """Maximum cost class authorized for one generation request."""

    CONFIGURED = "configured"
    ZERO_LOCAL = "zero_local"
    FREE_CLOUD = "free_cloud"
    PAID_LOW = "paid_low"


@dataclass(frozen=True)
class GenerationRequest:
    """Immutable routing constraints for one text-generation operation.

    Tools, search, audio, and device actions are deliberately not operations in
    this contract. They retain their own typed host/capability boundaries.
    """

    messages: tuple["LLMMessage", ...]
    operation: str = GenerationOperation.CONVERSATION.value
    privacy: str = GenerationPrivacy.CLOUD_OK.value
    cost_class: str = GenerationCost.CONFIGURED.value
    structured_output: bool = False
    structured_schema_json: str | None = None
    redaction_receipt: RedactionReceipt | None = None
    deadline_seconds: float | None = None
    correlation_id: str | None = None
    purpose: str | None = None
    temperature: float | None = None
    max_tokens: int | None = None

    def __post_init__(self) -> None:
        if isinstance(self.messages, LLMMessage):
            raise ValueError("GenerationRequest.messages must be a tuple of messages.")
        if self.operation not in {item.value for item in GenerationOperation}:
            raise ValueError(f"Unsupported generation operation: {self.operation}")
        if self.privacy not in {item.value for item in GenerationPrivacy}:
            raise ValueError(f"Unsupported generation privacy mode: {self.privacy}")
        if self.cost_class not in {item.value for item in GenerationCost}:
            raise ValueError(f"Unsupported generation cost class: {self.cost_class}")
        if (
            self.privacy == GenerationPrivacy.REDACT_FIRST.value
            and (
                self.redaction_receipt is None
                or not self.redaction_receipt.matches_messages(self.messages)
            )
        ):
            raise ValueError(
                "redact_first requests require a trusted receipt for the exact "
                "outbound non-system messages."
            )
        if (
            self.privacy != GenerationPrivacy.REDACT_FIRST.value
            and self.redaction_receipt is not None
        ):
            raise ValueError("Redaction receipts are valid only for redact_first.")
        if self.structured_schema_json is not None:
            if not self.structured_output:
                raise ValueError(
                    "structured_schema_json requires structured_output=True."
                )
            import json

            try:
                schema = json.loads(self.structured_schema_json)
            except (TypeError, ValueError, json.JSONDecodeError) as exc:
                raise ValueError("structured_schema_json must be valid JSON.") from exc
            if not isinstance(schema, dict):
                raise ValueError("structured_schema_json must describe a JSON object.")
        if self.deadline_seconds is not None and float(self.deadline_seconds) <= 0:
            raise ValueError("deadline_seconds must be positive when provided.")
        if self.correlation_id is not None:
            value = str(self.correlation_id).strip()
            if not value or len(value) > 128 or not all(
                char.isalnum() or char in "._:-" for char in value
            ):
                raise ValueError("correlation_id must be a bounded opaque identifier.")


@dataclass(frozen=True)
class ProviderRoute:
    """Public provider capability advertisement used by the router."""

    operations: frozenset[str] = field(default_factory=lambda: frozenset(
        item.value for item in GenerationOperation
    ))
    privacy_modes: frozenset[str] = field(default_factory=lambda: frozenset({
        GenerationPrivacy.CLOUD_OK.value,
        GenerationPrivacy.REDACT_FIRST.value,
    }))
    cost_class: str = GenerationCost.FREE_CLOUD.value
    structured_output: bool = False
    deadline_enforced: bool = False
    fallback_eligible: bool = True

    def supports(self, request: GenerationRequest) -> bool:
        if request.operation not in self.operations:
            return False
        if request.privacy not in self.privacy_modes:
            return False
        if request.structured_output and not self.structured_output:
            return False
        if request.deadline_seconds is not None and not self.deadline_enforced:
            return False
        allowed_costs = {
            GenerationCost.CONFIGURED.value: {
                GenerationCost.ZERO_LOCAL.value,
                GenerationCost.FREE_CLOUD.value,
                GenerationCost.PAID_LOW.value,
            },
            GenerationCost.ZERO_LOCAL.value: {GenerationCost.ZERO_LOCAL.value},
            GenerationCost.FREE_CLOUD.value: {
                GenerationCost.ZERO_LOCAL.value,
                GenerationCost.FREE_CLOUD.value,
            },
            GenerationCost.PAID_LOW.value: {GenerationCost.PAID_LOW.value},
        }
        return self.cost_class in allowed_costs[request.cost_class]


class LLMProviderError(RuntimeError):
    """Normalized failure raised at Mary's LLM provider boundary."""

    def __init__(
        self,
        message: str,
        *,
        provider: str = "unknown",
        retryable: bool = False,
        status_code: int | None = None,
        category: str = "provider_error",
    ) -> None:
        super().__init__(message)
        self.provider = provider
        self.retryable = bool(retryable)
        self.category = str(category or "provider_error")
        self.status_code = (
            int(status_code)
            if isinstance(status_code, int)
            and not isinstance(status_code, bool)
            and 100 <= status_code <= 599
            else None
        )


class LLMRateLimitError(LLMProviderError):
    """Provider usage/rate limit prevented generation."""

    def __init__(
        self,
        message: str,
        *,
        provider: str = "unknown",
        status_code: int | None = None,
    ) -> None:
        super().__init__(
            message,
            provider=provider,
            retryable=True,
            status_code=status_code,
            category="rate_limit",
        )


@dataclass
class LLMMessage:
    """A single message sent to an LLM."""

    role: str
    content: str


@dataclass
class LLMResponse:
    """
    Standardized response returned by an LLM provider.

    Provider-specific response objects should be converted into this format
    before reaching the rest of Mary's architecture.
    """

    content: str

    provider: str
    model: str

    finish_reason: str | None = None

    usage: dict[str, Any] = field(
        default_factory=dict
    )

    raw: Any = None


class LLMInterface(ABC):
    """
    Abstract interface for language-model providers.
    """

    def route_capabilities(self) -> ProviderRoute:
        """Advertise supported text operations and fallback eligibility."""

        return ProviderRoute()

    def generate_constrained(
        self,
        request: GenerationRequest,
        *,
        timeout_seconds: float | None = None,
    ) -> LLMResponse:
        """Generate while receiving the complete router request contract.

        Providers advertising ``deadline_enforced=True`` must enforce
        ``timeout_seconds`` themselves. The compatibility implementation is
        intentionally unavailable for deadline-bound work.
        """

        if timeout_seconds is not None:
            raise LLMProviderError(
                "provider_does_not_enforce_deadlines",
                provider=self.provider_name(),
                retryable=False,
                category="unsupported_constraint",
            )
        return self.generate(
            list(request.messages),
            temperature=0.7 if request.temperature is None else request.temperature,
            max_tokens=2048 if request.max_tokens is None else request.max_tokens,
        )

    @abstractmethod
    def generate(
        self,
        messages: list[LLMMessage],
        temperature: float = 0.7,
        max_tokens: int = 2048,
    ) -> LLMResponse:
        """
        Generate a response from the language model.
        """

        raise NotImplementedError

    @abstractmethod
    def is_available(self) -> bool:
        """
        Return whether the provider is configured and available.
        """

        raise NotImplementedError

    @abstractmethod
    def provider_name(self) -> str:
        """
        Return the provider's name.
        """

        raise NotImplementedError

    @abstractmethod
    def model_name(self) -> str:
        """
        Return the configured model name.
        """

        raise NotImplementedError


def generation_correlation_id(scope: str) -> str:
    """Create a process-local opaque correlation identifier."""

    prefix = "".join(
        char if char.isalnum() or char in "._:-" else "-"
        for char in str(scope or "generation").strip().lower()
    )[:48].strip("-") or "generation"
    return f"{prefix}:{uuid4().hex}"


def dispatch_generation(
    llm: Any,
    request: GenerationRequest,
    *,
    provider: str | None = None,
    route: str | None = None,
) -> LLMResponse:
    """Use the typed route API while preserving structural test adapters."""

    constrained = getattr(llm, "generate_request", None)
    if callable(constrained):
        return constrained(request, provider=provider, route=route)
    return llm.generate(
        messages=list(request.messages),
        temperature=0.7 if request.temperature is None else request.temperature,
        max_tokens=2048 if request.max_tokens is None else request.max_tokens,
    )