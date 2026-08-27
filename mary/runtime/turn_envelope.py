"""
MaryV2 - Ephemeral Turn Envelope

Carries a tiny, bounded set of transport/session facts into Mary's per-turn
context. This is context-only metadata: it is not identity, memory, relationship
authority, or a durable state store.

Unknown metadata is intentionally discarded so transport secrets or arbitrary
client payload fields cannot leak into Mary's cognitive prompt.
"""

from __future__ import annotations

import re
from typing import Any, Mapping


_IDENTIFIER_LIMITS = {
    "surface": 64,
    "transport": 64,
    "conversation_id": 160,
    "device_id": 160,
    "requested_mode": 32,
    "turn_id": 160,
}


def _safe_identifier(
    value: Any,
    *,
    limit: int,
) -> str | None:
    text = str(
        value
        or ""
    ).strip()

    if not text:
        return None

    text = re.sub(
        r"[^A-Za-z0-9._:/-]+",
        "_",
        text,
    )

    text = text.strip(
        "_"
    )

    if not text:
        return None

    return text[:limit]


def build_turn_envelope(
    metadata: Mapping[str, Any] | None,
) -> dict[str, Any]:
    """Build the model-safe ephemeral envelope for one Mary turn."""

    source = dict(
        metadata
        or {}
    )

    envelope: dict[str, Any] = {
        "authority": "context_only",
        "persistence": "ephemeral",
    }

    for key, limit in _IDENTIFIER_LIMITS.items():
        if key not in source:
            continue

        value = _safe_identifier(
            source.get(
                key
            ),
            limit=limit,
        )

        if value is not None:
            envelope[key] = value

    if "voice_input" in source:
        envelope[
            "voice_input"
        ] = bool(
            source.get(
                "voice_input"
            )
        )

    return envelope


def attach_turn_envelope(
    context: dict[str, Any],
    turn_context: Mapping[str, Any] | None,
) -> dict[str, Any]:
    """Attach a bounded turn envelope to Mary's existing runtime context."""

    envelope = build_turn_envelope(
        turn_context
    )

    useful_keys = set(
        envelope
    ) - {
        "authority",
        "persistence",
    }

    if not useful_keys:
        return context

    mind_state = context.setdefault(
        "mind_state",
        {},
    )

    if not isinstance(
        mind_state,
        dict,
    ):
        return context

    runtime_context = mind_state.setdefault(
        "runtime_context",
        {},
    )

    if not isinstance(
        runtime_context,
        dict,
    ):
        return context

    runtime_context[
        "turn"
    ] = envelope

    return context
