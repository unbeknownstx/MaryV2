"""Browser-context sensor adapter.

A browser extension/node may submit bounded page/media context here. The
adapter strips risky/raw fields and forwards objective descriptions through the
existing PerceptionDirector; it cannot write memory or speak as Mary.
"""
from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any
from urllib.parse import urlsplit


@dataclass(frozen=True)
class BrowserContext:
    page_title: str = ""
    url: str = ""
    visible_text_summary: str = ""
    video_subtitle_segment: str = ""
    media_state: str = ""
    source: str = "browser_node"
    metadata: dict[str, Any] = field(default_factory=dict)


class BrowserContextSensor:
    VERSION = "13.6"

    def __init__(self, perception_director: Any) -> None:
        self.perception = perception_director

    @staticmethod
    def _domain(url: str) -> str:
        try:
            return (urlsplit(str(url)).hostname or "")[:180]
        except Exception:
            return ""

    def ingest(
        self,
        context: BrowserContext,
        *,
        importance: float = 0.45,
    ):
        parts: list[str] = []
        if context.page_title.strip():
            parts.append(f"Page: {context.page_title.strip()[:240]}")
        domain = self._domain(context.url)
        if domain:
            parts.append(f"Domain: {domain}")
        if context.media_state.strip():
            parts.append(f"Media: {context.media_state.strip()[:120]}")
        if context.video_subtitle_segment.strip():
            parts.append(
                f"Subtitle: {context.video_subtitle_segment.strip()[:500]}"
            )
        if context.visible_text_summary.strip():
            parts.append(
                f"Visible content: {context.visible_text_summary.strip()[:700]}"
            )
        if not parts:
            raise ValueError("browser context contains no objective content")
        metadata = {
            "url_domain": domain,
            "page_title": context.page_title[:240],
            "media_state": context.media_state[:120],
        }
        blocked = {"token", "authorization", "api_key", "apikey", "secret", "password", "cookie", "session"}
        metadata.update({
            str(key)[:60]: str(value)[:160]
            for key, value in list(dict(context.metadata or {}).items())[:8]
            if str(key).strip().casefold() not in blocked
        })
        return self.perception.observe(
            " | ".join(parts),
            modality="screen",
            source=str(context.source or "browser_node")[:100],
            confidence=0.9,
            importance=max(0.0, min(1.0, float(importance))),
            metadata=metadata,
        )
