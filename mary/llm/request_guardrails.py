"""Content-safe request budgeting helpers for MaryV2 13.61.

Independently adapts useful gateway patterns: conservative input estimation,
a capped output reservation for routing, and explicit per-request budget checks.
This module never stores prompt content and never changes Mary's authority.
"""
from __future__ import annotations

from dataclasses import dataclass

VERSION = "13.61"
DEFAULT_OUTPUT_RESERVE = 1000
MAX_OUTPUT_RESERVE = 2000


def estimate_text_tokens(text: str) -> int:
    """Cheap conservative routing estimate; not billing/tokenizer authority."""
    return max(0, (len(str(text)) + 3) // 4)


def reserve_output_tokens(requested: int | None) -> int:
    try:
        value = DEFAULT_OUTPUT_RESERVE if requested is None else max(1, int(requested))
    except (TypeError, ValueError):
        value = DEFAULT_OUTPUT_RESERVE
    return min(MAX_OUTPUT_RESERVE, value)


@dataclass(frozen=True)
class RequestBudgetDecision:
    accepted: bool
    estimated_input_tokens: int
    reserved_output_tokens: int
    effective_max_tokens: int
    reason: str = "ok"

    def public_dict(self) -> dict[str, object]:
        return {
            "version": VERSION,
            "accepted": self.accepted,
            "estimated_input_tokens": self.estimated_input_tokens,
            "reserved_output_tokens": self.reserved_output_tokens,
            "effective_max_tokens": self.effective_max_tokens,
            "reason": self.reason,
            "content_retained": False,
        }


def apply_request_budget(*, estimated_input_tokens: int, requested_max_tokens: int | None, total_budget: int | None) -> RequestBudgetDecision:
    input_tokens = max(0, int(estimated_input_tokens))
    reserve = reserve_output_tokens(requested_max_tokens)
    requested = reserve if requested_max_tokens is None else max(1, int(requested_max_tokens))
    if total_budget is None:
        return RequestBudgetDecision(True, input_tokens, reserve, requested)
    budget = max(1, int(total_budget))
    remaining = budget - input_tokens
    if remaining <= 0:
        return RequestBudgetDecision(False, input_tokens, reserve, 0, "input_budget_exhausted")
    return RequestBudgetDecision(True, input_tokens, min(reserve, remaining), min(requested, remaining))
