"""Fail-open/fail-safe fidelity checks for disposable prompt projections.

Canonical transcript/state is never modified. A proposed compressed projection
is accepted only when high-risk literals and creator constraints survive.
"""
from __future__ import annotations

import re
from dataclasses import dataclass

VERSION = "13.61"
_NUMBER = re.compile(r"(?<![\w.])-?\d+(?:\.\d+)?(?![\w.])")
_JSON_KEY = re.compile(r'"([^"\\]{1,96})"\s*:')
_CONSTRAINT = re.compile(r"(?im)^.*\b(?:must|never|do not|don't|only|without|keep|preserve|required|exactly)\b.*$")
_DIFF = re.compile(r"(?m)^@@[^\n]*@@$")


def _values(pattern: re.Pattern[str], text: str) -> set[str]:
    found = pattern.findall(text)
    return {str(item).strip() for item in found if str(item).strip()}


@dataclass(frozen=True)
class FidelityDecision:
    accepted: bool
    reason: str
    numeric_preserved: bool
    json_key_survival: float
    constraints_preserved: bool
    diff_hunks_preserved: bool

    def public_dict(self) -> dict[str, object]:
        return {**self.__dict__, "version": VERSION, "content_retained": False}


def check_projection_fidelity(before: str, after: str) -> FidelityDecision:
    source, projected = str(before), str(after)
    if len(projected) >= len(source):
        return FidelityDecision(False, "no_compaction", True, 1.0, True, True)
    nums = _values(_NUMBER, source)
    numeric_ok = nums.issubset(_values(_NUMBER, projected))
    keys = _values(_JSON_KEY, source)
    projected_keys = _values(_JSON_KEY, projected)
    key_survival = 1.0 if not keys else len(keys & projected_keys) / len(keys)
    constraints = _values(_CONSTRAINT, source)
    constraints_ok = constraints.issubset(_values(_CONSTRAINT, projected))
    hunks = _values(_DIFF, source)
    hunks_ok = hunks.issubset(_values(_DIFF, projected))
    accepted = numeric_ok and key_survival >= 0.9 and constraints_ok and hunks_ok
    return FidelityDecision(accepted, "ok" if accepted else "fidelity", numeric_ok, key_survival, constraints_ok, hunks_ok)
