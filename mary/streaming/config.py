"""Secret-safe combined view of Mary's existing Twitch/OBS policies."""
from __future__ import annotations

from dataclasses import dataclass
import os

from mary.integrations.obs import obs_policy_from_environment
from mary.integrations.twitch import twitch_policy_from_environment


@dataclass(frozen=True)
class PerformerConfig:
    twitch_enabled: bool
    twitch_mode: str
    approved_channels: tuple[str, ...]
    twitch_write_chat: bool
    twitch_credentials_configured: bool
    obs_enabled: bool
    obs_host: str
    obs_port: int
    obs_allow_scene_switch: bool
    obs_password_configured: bool

    @classmethod
    def from_env(cls) -> "PerformerConfig":
        twitch = twitch_policy_from_environment()
        obs = obs_policy_from_environment()
        broadcaster = (
            os.getenv("MARY_TWITCH_BROADCASTER_USER_ID", "").strip()
            or os.getenv("MARY_TWITCH_BROADCASTER_ID", "").strip()
        )
        user_id = (
            os.getenv("MARY_TWITCH_USER_ID", "").strip()
            or os.getenv("MARY_TWITCH_BOT_USER_ID", "").strip()
        )
        return cls(
            twitch_enabled=twitch.enabled,
            twitch_mode=twitch.mode,
            approved_channels=twitch.approved_channels,
            twitch_write_chat=twitch.write_chat,
            twitch_credentials_configured=all(
                bool(value)
                for value in (
                    os.getenv("MARY_TWITCH_CLIENT_ID", "").strip(),
                    os.getenv("MARY_TWITCH_OAUTH_TOKEN", "").strip(),
                    broadcaster,
                    user_id,
                )
            ),
            obs_enabled=obs.enabled,
            obs_host=obs.host,
            obs_port=obs.port,
            obs_allow_scene_switch=obs.allow_scene_switch,
            obs_password_configured=bool(os.getenv("MARY_OBS_PASSWORD", "").strip()),
        )

    def status(self) -> dict[str, object]:
        return {
            "twitch": {
                "enabled": self.twitch_enabled,
                "mode": self.twitch_mode,
                "write_chat": self.twitch_write_chat,
                "approved_channels": list(self.approved_channels),
                "credentials_configured": self.twitch_credentials_configured,
            },
            "obs": {
                "enabled": self.obs_enabled,
                "endpoint": f"{self.obs_host}:{self.obs_port}",
                "allow_scene_switch": self.obs_allow_scene_switch,
                "password_configured": self.obs_password_configured,
            },
            "policy_source": "mary.integrations.twitch/obs",
        }
