"""Provider-neutral creator lab for making things around canonical Mary.

The lab turns a creator-owned/approved asset plus intent into a bounded creative
packet. It never claims to have visually inspected an asset unless a perception
capability supplied a description, never executes external providers, and never
owns Mary identity, memory, relationship, or character state.
"""
from __future__ import annotations

from typing import Any, Mapping
from uuid import uuid4


def _text(value: Any, limit: int) -> str:
    return " ".join(str(value or "").split()).strip()[: max(0, int(limit))]


def _strings(value: Any, *, limit: int = 16, width: int = 500) -> list[str]:
    source = value if isinstance(value, (list, tuple, set)) else []
    return [clean for item in list(source)[:limit] if (clean := _text(item, width))]


def normalize_asset(value: Mapping[str, Any] | None) -> dict[str, Any]:
    raw = dict(value or {})
    return {
        "asset_id": _text(raw.get("asset_id") or f"creative_{uuid4().hex}", 120),
        "kind": _text(raw.get("kind") or "image", 40).lower(),
        "uri": _text(raw.get("uri"), 2_000),
        "creator_description": _text(raw.get("creator_description"), 2_000),
        "perception_description": _text(raw.get("perception_description"), 2_000),
        "provenance": _text(raw.get("provenance") or "creator_supplied", 80),
        "reference_only": bool(raw.get("reference_only", False)),
    }


def effective_asset_description(asset: Mapping[str, Any]) -> tuple[str, str]:
    """Return description + authority without pretending Mary saw unseen pixels."""
    perceived = _text(asset.get("perception_description"), 2_000)
    if perceived:
        return perceived, "perception_capability"
    creator = _text(asset.get("creator_description"), 2_000)
    if creator:
        return creator, "creator_description"
    return "", "unseen_asset"


def build_creator_packet(
    *,
    asset: Mapping[str, Any] | None,
    intent: Any = "",
    outputs: Any = None,
    tone: Any = "",
    platform: Any = "",
    duration_seconds: Any = 15,
    mary_speaks: bool = True,
    style_constraints: Any = None,
) -> dict[str, Any]:
    """Compile one asset into reusable caption/voice/video planning context."""
    item = normalize_asset(asset)
    description, description_source = effective_asset_description(item)
    requested = _strings(outputs or ["mary_caption", "mary_voice", "video_brief"], limit=12, width=80)
    try:
        seconds = max(1, min(600, int(duration_seconds)))
    except (TypeError, ValueError):
        seconds = 15

    shared = {
        "asset": item,
        "asset_description": description,
        "description_source": description_source,
        "intent": _text(intent, 2_000),
        "tone": _text(tone, 300),
        "platform": _text(platform, 80).lower(),
        "duration_seconds": seconds,
        "style_constraints": _strings(style_constraints, limit=24, width=500),
        "mary_speaks": bool(mary_speaks),
    }
    jobs: list[dict[str, Any]] = []

    if not description:
        jobs.append({
            "kind": "vision.describe",
            "requires_approval": False,
            "asset_ref": item.get("uri") or item.get("asset_id"),
            "purpose": "ground creative work in the supplied visual before Mary comments on it",
            "policy": "description is capability output, not canonical memory or creator biography",
        })

    if "mary_caption" in requested or "mary_script" in requested:
        jobs.append({
            "kind": "mary.author",
            "requires_approval": False,
            "surface": "creative",
            "input_authority": "context_only",
            "payload": shared,
            "policy": "canonical Mary authors the line; asset context does not become lived memory",
        })
    if mary_speaks and ("mary_voice" in requested or "mary_script" in requested):
        jobs.append({
            "kind": "voice.synthesize",
            "requires_approval": False,
            "input": "mary_authored_text",
            "delivery": "canonical_delivery_plan",
            "policy": "reuse Mary's existing voice/performance bridge",
        })
    if "image_variant" in requested:
        jobs.append({
            "kind": "image.generate",
            "requires_approval": True,
            "approval_reason": "external_or_consequential_capability",
            "payload": shared,
        })
    if "video_brief" in requested or "video" in requested:
        jobs.append({
            "kind": "video.render",
            "requires_approval": True,
            "approval_reason": "external_or_consequential_capability",
            "payload": {**shared, "voice_input": "rendered_mary_voice" if mary_speaks else ""},
        })

    return {
        "version": "1",
        "authority": "creator_directed_artifact_planning",
        "identity_owner": False,
        "memory_owner": False,
        "asset": item,
        "description_source": description_source,
        "requested_outputs": requested,
        "jobs": jobs,
        "ready_for_mary_authoring": bool(description),
        "execution_authorized": False,
        "publishing_authorized": False,
        "policy": (
            "Creator Lab coordinates perception, canonical Mary authorship, voice, and replaceable "
            "creative workers without transferring Mary identity or silently executing/publishing."
        ),
    }
