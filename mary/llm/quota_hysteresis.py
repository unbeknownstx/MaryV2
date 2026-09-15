"""Quota-pressure hysteresis for MaryV2 13.64."""
from __future__ import annotations
from dataclasses import dataclass

VERSION = "13.64"

@dataclass
class QuotaHysteresis:
    enter_pressure_below: float = 0.15
    leave_pressure_above: float = 0.25
    pressured: bool = False

    def update(self, remaining_fraction: float | None) -> bool:
        if remaining_fraction is None:
            return self.pressured
        value = float(remaining_fraction)
        if not 0.0 <= value <= 1.0:
            raise ValueError("remaining_fraction must be between 0 and 1")
        if self.pressured:
            if value >= self.leave_pressure_above:
                self.pressured = False
        elif value <= self.enter_pressure_below:
            self.pressured = True
        return self.pressured
