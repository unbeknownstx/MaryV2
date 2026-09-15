"""Per-request failover circuit breaker for MaryV2 13.62."""
from __future__ import annotations

from dataclasses import dataclass

VERSION = "13.62"


@dataclass
class FailoverBudget:
    """Bound consecutive upstream failures without changing provider policy."""

    max_attempts: int = 4
    max_consecutive_failures: int = 3
    attempts: int = 0
    consecutive_failures: int = 0

    def __post_init__(self) -> None:
        self.max_attempts = max(1, min(16, int(self.max_attempts)))
        self.max_consecutive_failures = max(1, min(self.max_attempts, int(self.max_consecutive_failures)))

    def may_attempt(self) -> bool:
        return self.attempts < self.max_attempts and self.consecutive_failures < self.max_consecutive_failures

    def begin_attempt(self) -> None:
        if not self.may_attempt():
            raise RuntimeError("provider failover budget exhausted")
        self.attempts += 1

    def success(self) -> None:
        self.consecutive_failures = 0

    def failure(self) -> None:
        self.consecutive_failures += 1

    def snapshot(self) -> dict[str, object]:
        return {
            "version": VERSION,
            "attempts": self.attempts,
            "consecutive_failures": self.consecutive_failures,
            "remaining_attempts": max(0, self.max_attempts - self.attempts),
            "exhausted": not self.may_attempt(),
            "content_retained": False,
        }
