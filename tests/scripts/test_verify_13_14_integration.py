from __future__ import annotations

from scripts.verify_13_14_integration import main


def test_13_14_convergence_verifier_passes() -> None:
    assert main() == 0
