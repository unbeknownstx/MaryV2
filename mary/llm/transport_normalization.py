"""Multimodal transport normalization and request capability prefilter, 13.64."""
from __future__ import annotations
from dataclasses import dataclass
from urllib.parse import urlparse

VERSION = "13.64"
_ALLOWED_IMAGE_MIME = frozenset({"image/png", "image/jpeg", "image/webp", "image/gif"})

@dataclass(frozen=True)
class ImagePart:
    url: str
    mime_type: str | None = None
    detail: str = "auto"

    def __post_init__(self) -> None:
        value = str(self.url).strip()
        parsed = urlparse(value)
        if not (value.startswith("data:image/") or parsed.scheme in {"http", "https"}):
            raise ValueError("image must use data:image or http(s) transport")
        if self.mime_type is not None and self.mime_type not in _ALLOWED_IMAGE_MIME:
            raise ValueError("unsupported image mime type")
        if self.detail not in {"auto", "low", "high"}:
            raise ValueError("unsupported image detail")

    def openai_part(self) -> dict[str, object]:
        return {"type": "image_url", "image_url": {"url": self.url, "detail": self.detail}}

@dataclass(frozen=True)
class RequestCapabilities:
    vision: bool = False
    tools: bool = False
    structured_json: bool = False
    reasoning: bool = False

@dataclass(frozen=True)
class ProviderCapabilities:
    vision: bool = False
    tools: bool = False
    structured_json: bool = False
    reasoning: bool = False

def supports_request(provider: ProviderCapabilities, request: RequestCapabilities) -> bool:
    return ((not request.vision or provider.vision) and (not request.tools or provider.tools) and (not request.structured_json or provider.structured_json) and (not request.reasoning or provider.reasoning))

def prefilter(providers: list[str], evidence: dict[str, ProviderCapabilities], request: RequestCapabilities) -> list[str]:
    """Unknown capability evidence is not promoted to measured support."""
    return [name for name in providers if name in evidence and supports_request(evidence[name], request)]
