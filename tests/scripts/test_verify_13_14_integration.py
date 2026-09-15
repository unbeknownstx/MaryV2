from __future__ import annotations

from scripts.check_13_14_integration import main


def test_13_14_convergence_check_passes() -> None:
    assert main() == 0
