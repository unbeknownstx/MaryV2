"""Canonical capability names for stream/game embodiment nodes.

These are execution contracts only. NodeRegistry remains the route/availability
owner and Mary Core remains cognition/identity authority.
"""
from __future__ import annotations

from dataclasses import dataclass


@dataclass(frozen=True)
class StreamCapability:
    name: str
    consequential: bool
    description: str


CAPABILITIES = (
    StreamCapability("obs.scene.switch", True, "Switch an OBS scene through an enrolled capability node."),
    StreamCapability("obs.overlay.update", False, "Update bounded stream overlay presentation state."),
    StreamCapability("vts.expression.set", False, "Set a VTube Studio expression chosen by Mary's performance layer."),
    StreamCapability("vts.motion.trigger", False, "Trigger an approved VTube Studio motion/hotkey."),
    StreamCapability("stream.donation.event", False, "Ingest a donation/subscription event as untrusted social context."),
    StreamCapability("desktop_audio.transcribe", False, "Return bounded transcript context from local desktop audio."),
    StreamCapability("minecraft.observe", False, "Return structured game/world observations."),
    StreamCapability("minecraft.act", True, "Execute a bounded high-level Minecraft intent; low-level controls stay in the node."),
)


class StreamCapabilityCatalog:
    VERSION = "1"

    def names(self) -> tuple[str, ...]:
        return tuple(item.name for item in CAPABILITIES)

    def snapshot(self) -> dict:
        return {
            "version": self.VERSION,
            "capabilities": [item.__dict__ for item in CAPABILITIES],
            "authority": "execution descriptors only; no Mary state ownership",
        }
