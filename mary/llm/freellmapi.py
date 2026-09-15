"""Optional FreeLLMAPI gateway adapter for MaryV2 13.60.

FreeLLMAPI is treated as one replaceable cloud provider lane beneath Mary's
own authority/router. It never owns identity, memory, provider policy, or
canonical state.
"""
from __future__ import annotations

import os

from .providers.openai_compatible import OpenAICompatibleProvider


VERSION = "13.60"


def enabled() -> bool:
    return bool(os.getenv("MARY_FREELLMAPI_BASE_URL", "").strip())


def provider() -> OpenAICompatibleProvider:
    base_url = os.getenv("MARY_FREELLMAPI_BASE_URL", "").strip()
    if not base_url:
        raise RuntimeError("MARY_FREELLMAPI_BASE_URL is not configured")
    # Reuse Mary's existing bounded OpenAI-compatible provider seam. The gateway
    # credential remains an environment secret and is never placed in routing
    # diagnostics. Defaults are intentionally local/self-hosted friendly.
    return OpenAICompatibleProvider(
        provider_name="freellmapi",
        base_url=base_url.rstrip("/"),
        api_key=os.getenv("MARY_FREELLMAPI_API_KEY", "").strip() or None,
        model=os.getenv("MARY_FREELLMAPI_MODEL", "auto").strip() or "auto",
    )
