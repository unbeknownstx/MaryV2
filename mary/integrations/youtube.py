"""Explicit YouTube Data API integration for MaryV2.

This adapter is intentionally query-driven: it does nothing in the background
and it never turns search results into durable Mary memory.  Public search uses
an API key. OAuth/private-account features can be added later behind a separate
approval boundary.
"""
from __future__ import annotations

from dataclasses import dataclass
import json
import os
from typing import Any
from urllib.parse import urlencode
from urllib.request import Request, urlopen


@dataclass(frozen=True)
class YouTubePolicy:
    enabled: bool
    configured: bool
    max_results: int

    def to_dict(self) -> dict[str, Any]:
        return {
            "enabled": self.enabled,
            "configured": self.configured,
            "max_results": self.max_results,
            "mode": "explicit_public_search",
            "persistence": "ephemeral_until_creator_saves_to_research",
        }


class YouTubeSearch:
    BASE = "https://www.googleapis.com/youtube/v3"

    def __init__(self, *, api_key: str | None = None, enabled: bool | None = None) -> None:
        self.api_key = str(api_key or os.getenv("YOUTUBE_API_KEY", "")).strip()
        env_enabled = os.getenv("MARY_YOUTUBE_ENABLED", "false").strip().lower() in {"1", "true", "yes", "on"}
        self.enabled = env_enabled if enabled is None else bool(enabled)
        try:
            configured_max = int(os.getenv("MARY_YOUTUBE_MAX_RESULTS", "6"))
        except ValueError:
            configured_max = 6
        self.max_results = max(1, min(12, configured_max))

    @property
    def policy(self) -> YouTubePolicy:
        return YouTubePolicy(self.enabled, bool(self.api_key), self.max_results)

    def status(self) -> dict[str, Any]:
        return self.policy.to_dict()

    def search(self, query: str, *, max_results: int | None = None) -> list[dict[str, Any]]:
        if not self.enabled:
            raise RuntimeError("YouTube integration is disabled. Set MARY_YOUTUBE_ENABLED=true to enable explicit searches.")
        if not self.api_key:
            raise RuntimeError("YouTube API key is not configured. Set YOUTUBE_API_KEY.")
        value = str(query or "").strip()
        if not value:
            return []
        limit = max(1, min(self.max_results, int(max_results or self.max_results)))
        params = {
            "part": "snippet",
            "q": value,
            "type": "video",
            "maxResults": str(limit),
            "safeSearch": "moderate",
            "key": self.api_key,
        }
        payload = self._get("/search", params)
        results: list[dict[str, Any]] = []
        for item in payload.get("items", [])[:limit]:
            if not isinstance(item, dict):
                continue
            video_id = str((item.get("id") or {}).get("videoId") or "").strip()
            snippet = item.get("snippet") if isinstance(item.get("snippet"), dict) else {}
            if not video_id:
                continue
            thumbs = snippet.get("thumbnails") if isinstance(snippet.get("thumbnails"), dict) else {}
            thumb = thumbs.get("medium") or thumbs.get("default") or {}
            results.append({
                "video_id": video_id,
                "title": str(snippet.get("title") or "Untitled"),
                "channel": str(snippet.get("channelTitle") or ""),
                "published_at": str(snippet.get("publishedAt") or ""),
                "description": str(snippet.get("description") or "")[:500],
                "thumbnail": str(thumb.get("url") or ""),
                "url": f"https://www.youtube.com/watch?v={video_id}",
                "source": "youtube_data_api",
            })
        return results

    def _get(self, path: str, params: dict[str, str]) -> dict[str, Any]:
        url = f"{self.BASE}{path}?{urlencode(params)}"
        request = Request(url, headers={"User-Agent": "MaryV2/12.11"})
        with urlopen(request, timeout=12) as response:  # nosec - fixed Google API host
            raw = response.read(2_000_000)
        data = json.loads(raw.decode("utf-8"))
        return data if isinstance(data, dict) else {}
