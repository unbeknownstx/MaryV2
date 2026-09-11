"""Secret-safe configuration for optional streaming adapters."""
from __future__ import annotations

from dataclasses import dataclass
import os

_TRUE = {"1", "true", "yes", "on", "enabled"}


def _enabled(name: str) -> bool:
    return os.getenv(name, "").strip().casefold() in _TRUE


def _csv(name: str) -> tuple[str, ...]:
    return tuple(value.strip().casefold() for value in os.getenv(name, "").split(",") if value.strip())


@dataclass(frozen=True)
class PerformerConfig:
    twitch_enabled: bool
    twitch_mode: str
    approved_channels: tuple[str, ...]
    twitch_credentials_configured: bool
    obs_enabled: bool
    obs_host: str
    obs_port: int
    obs_password_configured: bool

    @classmethod
    def from_env(cls) -> "PerformerConfig":
        mode = os.getenv("MARY_TWITCH_MODE", "listen").strip().casefold() or "listen"
        if mode not in {"listen", "interactive"}:
            mode = "listen"
        try:
            port = int(os.getenv("MARY_OBS_PORT", "4455") or 4455)
        except ValueError:
            port = 4455
        return cls(
            twitch_enabled=_enabled("MARY_SKILL_TWITCH"),
            twitch_mode=mode,
            approved_channels=_csv("MARY_TWITCH_APPROVED_CHANNELS"),
            twitch_credentials_configured=all(bool(os.getenv(name, "").strip()) for name in (
                "MARY_TWITCH_CLIENT_ID", "MARY_TWITCH_OAUTH_TOKEN", "MARY_TWITCH_BROADCASTER_ID"
            )),
            obs_enabled=_enabled("MARY_SKILL_OBS"),
            obs_host=os.getenv("MARY_OBS_HOST", "127.0.0.1").strip() or "127.0.0.1",
            obs_port=max(1, min(65535, port)),
            obs_password_configured=bool(os.getenv("MARY_OBS_PASSWORD", "").strip()),
        )

    def status(self) -> dict[str, object]:
        return {
            "twitch": {
                "enabled": self.twitch_enabled,
                "mode": self.twitch_mode,
                "approved_channels": list(self.approved_channels),
                "credentials_configured": self.twitch_credentials_configured,
            },
            "obs": {
                "enabled": self.obs_enabled,
                "endpoint": f"{self.obs_host}:{self.obs_port}",
                "password_configured": self.obs_password_configured,
            },
        }
