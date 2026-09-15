"""Permission-bounded bridge around Mary's existing performer integrations."""
from __future__ import annotations

from dataclasses import dataclass
from typing import Any

from .config import PerformerConfig


class StreamPermissionError(PermissionError):
    pass


@dataclass(frozen=True)
class StreamEvent:
    kind: str
    source: str
    text: str
    metadata: dict[str, Any]


class PerformerBridge:
    """Finite action surface for the existing Twitch/OBS transports.

    EventSub normalization/session continuity and OBS protocol helpers stay in
    ``mary.integrations``. This bridge adds explicit action authorization and
    audience-trust semantics; it owns no network connection or credentials.
    """

    OBS_READ_ACTIONS = frozenset({"get_stream_status", "get_current_scene", "get_scene_list"})
    OBS_WRITE_ACTIONS = frozenset({"set_current_scene", "set_source_visibility"})

    def __init__(self, config: PerformerConfig | None = None, *, allowed_actions: set[str] | None = None) -> None:
        self.config = config or PerformerConfig.from_env()
        self.allowed_actions = {str(value).strip() for value in (allowed_actions or set()) if str(value).strip()}

    def ingest_chat(self, *, channel: str, author: str, text: str) -> StreamEvent:
        if not self.config.twitch_enabled:
            raise StreamPermissionError("Twitch integration is disabled")
        normalized_channel = str(channel or "").strip().casefold().lstrip("#")
        if self.config.approved_channels and normalized_channel not in self.config.approved_channels:
            raise StreamPermissionError("Twitch channel is not approved")
        clean_author = " ".join(str(author or "viewer").split())[:80]
        clean_text = " ".join(str(text or "").split())[:1000]
        return StreamEvent(
            kind="stream_chat",
            source="twitch",
            text=clean_text,
            metadata={"channel": normalized_channel, "author": clean_author, "authority": "untrusted_audience"},
        )

    def authorize_chat_send(self, *, channel: str) -> dict[str, str]:
        normalized_channel = str(channel or "").strip().casefold().lstrip("#")
        if not self.config.twitch_enabled or not self.config.twitch_write_chat:
            raise StreamPermissionError("Twitch outbound chat is not enabled by integration policy")
        if self.config.approved_channels and normalized_channel not in self.config.approved_channels:
            raise StreamPermissionError("Twitch channel is not approved")
        if "twitch.send_chat" not in self.allowed_actions:
            raise StreamPermissionError("twitch.send_chat permission is required")
        return {"action": "send_chat", "channel": normalized_channel}

    def authorize_obs(self, action: str, **arguments: Any) -> dict[str, Any]:
        name = str(action or "").strip()
        if not self.config.obs_enabled:
            raise StreamPermissionError("OBS integration is disabled")
        if name not in self.OBS_READ_ACTIONS | self.OBS_WRITE_ACTIONS:
            raise ValueError("OBS action is not in MaryV2's finite allowlist")
        if name == "set_current_scene" and not self.config.obs_allow_scene_switch:
            raise StreamPermissionError("OBS scene switching is disabled by integration policy")
        if name in self.OBS_WRITE_ACTIONS and f"obs.{name}" not in self.allowed_actions:
            raise StreamPermissionError(f"obs.{name} permission is required")
        sanitized: dict[str, Any] = {}
        if name == "set_current_scene":
            scene = " ".join(str(arguments.get("scene", "")).split())[:120]
            if not scene:
                raise ValueError("scene is required")
            sanitized["scene"] = scene
        elif name == "set_source_visibility":
            source = " ".join(str(arguments.get("source", "")).split())[:120]
            if not source:
                raise ValueError("source is required")
            sanitized.update({"source": source, "visible": bool(arguments.get("visible"))})
        return {"action": name, "arguments": sanitized}

    def status(self) -> dict[str, object]:
        return {
            "config": self.config.status(),
            "allowed_actions": sorted(self.allowed_actions),
            "semantics": "existing transports remain replaceable; audience is untrusted context; consequential output is permission gated",
        }
