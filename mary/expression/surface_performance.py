"""Surface capability projection for Mary's canonical performance packet.

The PerformancePacket is the authoritative presentation score.  A renderer is
only a body/surface: it may realize the cues it supports and degrade the rest,
but it must never rewrite Mary's text, emotion, identity, memory, relationship,
or agency.

This module makes that adaptation explicit.  It is deliberately deterministic,
provider-neutral and side-effect free so Desktop, PWA, native iPhone, stream
and future Unity/VR bodies can all report what they can actually render.
"""
from __future__ import annotations

from dataclasses import asdict, dataclass
from typing import Any, Mapping


@dataclass(frozen=True)
class SurfacePerformanceCapabilities:
    """Presentation affordances offered by one surface/body."""

    surface: str
    expression_cues: bool = False
    gaze_cues: bool = False
    head_motion: bool = False
    semantic_motion: bool = False
    motion_assets: bool = False
    lip_sync: bool = False
    voice_direction: bool = True
    scene_context: bool = False
    lighting_control: bool = False
    transparent_overlay: bool = False
    capture: bool = False
    locomotion: bool = False
    vr: bool = False

    def to_dict(self) -> dict[str, Any]:
        return asdict(self)


_SURFACE_ALIASES = {
    "desktop": "desktop",
    "windows_desktop": "desktop",
    "mac_desktop": "desktop",
    "macos_desktop": "desktop",
    "pwa": "mobile_web",
    "mobile": "mobile_web",
    "mobile_surface": "mobile_web",
    "mobile_web": "mobile_web",
    "ios": "ios_native",
    "ios_native": "ios_native",
    "iphone": "ios_native",
    "stream": "stream",
    "obs": "stream",
    "vr": "vr",
    "unity": "vr",
}

_PROFILES: dict[str, SurfacePerformanceCapabilities] = {
    "desktop": SurfacePerformanceCapabilities(
        surface="desktop",
        expression_cues=True,
        gaze_cues=True,
        head_motion=True,
        semantic_motion=True,
        motion_assets=False,  # current renderer uses bounded procedural poses
        lip_sync=True,
        voice_direction=True,
        scene_context=True,
        lighting_control=True,
        capture=True,
    ),
    "mobile_web": SurfacePerformanceCapabilities(
        surface="mobile_web",
        expression_cues=True,
        gaze_cues=True,
        voice_direction=True,
    ),
    "ios_native": SurfacePerformanceCapabilities(
        surface="ios_native",
        expression_cues=True,
        gaze_cues=True,
        head_motion=True,
        voice_direction=True,
    ),
    "stream": SurfacePerformanceCapabilities(
        surface="stream",
        expression_cues=True,
        gaze_cues=True,
        semantic_motion=True,
        voice_direction=True,
        scene_context=True,
    ),
    # Future VR/Unity body. Keep unsupported affordances false until a real
    # renderer/node reports them instead of advertising aspirational features.
    "vr": SurfacePerformanceCapabilities(
        surface="vr",
        voice_direction=True,
        scene_context=True,
    ),
    "generic": SurfacePerformanceCapabilities(surface="generic"),
}


def normalize_surface(value: Any) -> str:
    surface = str(value or "generic").strip().lower().replace("-", "_")
    return _SURFACE_ALIASES.get(surface, surface if surface in _PROFILES else "generic")


def capabilities_for_surface(
    surface: Any,
    overrides: Mapping[str, Any] | None = None,
) -> SurfacePerformanceCapabilities:
    """Return truthful capabilities for a known presentation surface.

    Optional overrides are intended for a negotiated renderer/node handshake.
    Only existing capability fields may be changed; unknown keys are ignored.
    """

    normalized = normalize_surface(surface)
    base = _PROFILES.get(normalized, _PROFILES["generic"])
    if not overrides:
        return base

    values = base.to_dict()
    for key, value in dict(overrides).items():
        if key == "surface" or key not in values:
            continue
        values[key] = bool(value)
    values["surface"] = normalized
    return SurfacePerformanceCapabilities(**values)


def project_performance_packet(
    packet: Mapping[str, Any] | None,
    *,
    surface: Any,
    capability_overrides: Mapping[str, Any] | None = None,
) -> dict[str, Any]:
    """Describe how a surface can realize an existing PerformancePacket.

    The canonical packet is never mutated.  The projection contains only
    presentation instructions/fallbacks and therefore cannot become evidence
    about Mary's identity or internal state.
    """

    canonical = dict(packet or {})
    capabilities = capabilities_for_surface(surface, capability_overrides)
    delivery = dict(canonical.get("delivery") or {})
    segments = [
        dict(item)
        for item in list(canonical.get("segments") or [])[:16]
        if isinstance(item, Mapping)
    ]
    motion_cues = [
        dict(item)
        for item in list(canonical.get("motion_cues") or [])[:16]
        if isinstance(item, Mapping)
    ]
    reaction = dict(canonical.get("pre_reaction") or {})

    requested: list[str] = []
    if delivery.get("avatar_expression") or reaction.get("expression"):
        requested.append("expression_cues")
    if delivery.get("gaze_style") or reaction.get("gaze_style"):
        requested.append("gaze_cues")
    if delivery.get("head_style") or reaction.get("head_style"):
        requested.append("head_motion")
    if motion_cues:
        requested.append("semantic_motion")
        if any(str(item.get("asset_uri") or "").strip() for item in motion_cues):
            requested.append("motion_assets")
    if canonical.get("spoken_text") or delivery:
        requested.append("voice_direction")

    supported = [name for name in requested if bool(getattr(capabilities, name, False))]
    degraded = [name for name in requested if name not in supported]

    fallback: dict[str, str] = {}
    if "expression_cues" in degraded:
        fallback["expression_cues"] = "retain text/voice; surface may show a non-facial mood indicator"
    if "gaze_cues" in degraded:
        fallback["gaze_cues"] = "ignore gaze safely"
    if "head_motion" in degraded:
        fallback["head_motion"] = "ignore head motion safely"
    if "semantic_motion" in degraded:
        fallback["semantic_motion"] = "retain expression/voice without body motion"
    if "motion_assets" in degraded:
        fallback["motion_assets"] = "use semantic/procedural motion when supported"
    if "voice_direction" in degraded:
        fallback["voice_direction"] = "render canonical text without speech styling"

    return {
        "version": "1",
        "surface": capabilities.surface,
        "capabilities": capabilities.to_dict(),
        "requested_channels": requested,
        "supported_channels": supported,
        "degraded_channels": degraded,
        "fallbacks": fallback,
        "performance_packet_version": str(canonical.get("version") or ""),
        "segment_count": len(segments),
        "motion_cue_count": len(motion_cues),
        "authority": "surface_presentation_only",
        "identity_owner": "mary_core",
        "persistence": "none",
        "policy": (
            "surface realizes or degrades canonical performance cues; "
            "surface never becomes character/cognition authority"
        ),
    }
