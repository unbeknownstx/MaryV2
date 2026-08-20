"""Small deterministic helpers for enforcing hard collection bounds."""

from __future__ import annotations

from datetime import datetime
from typing import Any, Callable, MutableSequence, TypeVar

T = TypeVar("T")


def clip_text(value: Any, limit: int) -> str:
    """Return bounded text while preserving both ends of unusually long input."""

    text = str(value or "").strip()
    limit = max(1, int(limit))
    if len(text) <= limit:
        return text
    marker = " …[compacted]… "
    available = max(0, limit - len(marker))
    head = available // 2
    tail = available - head
    if tail <= 0:
        return text[:limit]
    return text[:head].rstrip() + marker + text[-tail:].lstrip()



def bounded_payload(
    value: Any,
    *,
    text_limit: int = 2000,
    item_limit: int = 64,
    depth_limit: int = 4,
    _depth: int = 0,
) -> Any:
    """Return a JSON-friendly bounded copy of arbitrary metadata.

    Metadata is useful for provenance, but it must never be a loophole around
    MaryV2's storage/context ceilings. Deep or huge structures are summarized
    rather than recursively retained forever.
    """

    if value is None or isinstance(value, (bool, int, float)):
        return value
    if isinstance(value, str):
        return clip_text(value, text_limit)
    if _depth >= max(1, int(depth_limit)):
        return "[metadata compacted]"

    next_depth = _depth + 1
    limit = max(1, int(item_limit))
    if isinstance(value, dict):
        result: dict[str, Any] = {}
        for index, (key, item) in enumerate(value.items()):
            if index >= limit:
                result["__compacted_items__"] = max(0, len(value) - limit)
                break
            result[clip_text(key, 160)] = bounded_payload(
                item,
                text_limit=text_limit,
                item_limit=item_limit,
                depth_limit=depth_limit,
                _depth=next_depth,
            )
        return result
    if isinstance(value, (list, tuple, set)):
        items = list(value)
        result = [
            bounded_payload(
                item,
                text_limit=text_limit,
                item_limit=item_limit,
                depth_limit=depth_limit,
                _depth=next_depth,
            )
            for item in items[:limit]
        ]
        if len(items) > limit:
            result.append(f"[{len(items) - limit} metadata items compacted]")
        return result

    return clip_text(value, text_limit)

def timestamp_value(value: Any) -> float:
    """Best-effort sortable timestamp; invalid/missing values rank as oldest."""

    if isinstance(value, datetime):
        try:
            return value.timestamp()
        except (ValueError, OSError):
            return 0.0
    text = str(value or "").strip()
    if not text:
        return 0.0
    try:
        return datetime.fromisoformat(text.replace("Z", "+00:00")).timestamp()
    except (TypeError, ValueError, OSError):
        return 0.0


def enforce_capacity(
    items: MutableSequence[T],
    capacity: int,
    *,
    keep_score: Callable[[T], tuple[Any, ...]] | None = None,
    protected: Callable[[T], bool] | None = None,
) -> int:
    """Trim ``items`` in place and return the number removed.

    ``keep_score`` returns a tuple where larger values mean the record is more
    valuable to retain. Protected records are avoided while possible, but the
    hard ceiling always wins so no collection can become infinite.
    """

    capacity = max(1, int(capacity))
    removed = 0
    score = keep_score or (lambda _item: (0,))

    while len(items) > capacity:
        candidate_indices = [
            index for index, item in enumerate(items)
            if protected is None or not protected(item)
        ]
        if not candidate_indices:
            candidate_indices = list(range(len(items)))
        victim = min(candidate_indices, key=lambda index: score(items[index]))
        del items[victim]
        removed += 1

    return removed
