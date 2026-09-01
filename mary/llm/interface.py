"""
MaryV2 LLM Interface

Defines the contract that every language-model provider must implement.

The rest of Mary should depend on this interface rather than directly
depending on Groq, OpenAI, or any future provider.
"""

from abc import ABC, abstractmethod
from dataclasses import dataclass, field
from typing import Any


class LLMProviderError(RuntimeError):
    """Normalized failure raised at Mary's LLM provider boundary."""

    def __init__(
        self,
        message: str,
        *,
        provider: str = "unknown",
        retryable: bool = False,
        status_code: int | None = None,
    ) -> None:
        super().__init__(message)
        self.provider = provider
        self.retryable = bool(retryable)
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