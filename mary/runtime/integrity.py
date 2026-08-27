"""
MaryV2 - Application Composition Integrity

Read-only checks for the canonical MaryApplication composition.

This module does not create Mary, mutate state, select providers, or repair
anything. It only verifies that the application composition respects the
ONE-MARY runtime boundary.
"""

from __future__ import annotations

from typing import Any

from mary.runtime.mary_stage import MaryStage


def application_integrity_report(
    application: Any,
) -> dict[str, Any]:
    """
    Return a read-only report for one MaryApplication composition.

    The report verifies object identity rather than names or source formatting.
    It intentionally does not inspect Mary's internal subsystem semantics yet;
    those integration checks are layered on separately.
    """

    mary = getattr(
        application,
        "mary",
        None,
    )
    ecosystem = getattr(
        application,
        "ecosystem",
        None,
    )
    state = getattr(
        application,
        "state",
        None,
    )
    pipeline = getattr(
        application,
        "pipeline",
        None,
    )

    stages = list(
        getattr(
            pipeline,
            "stages",
            (),
        )
        or ()
    )

    mary_stages = [
        stage
        for stage in stages
        if isinstance(
            stage,
            MaryStage,
        )
    ]

    checks = {
        "application_has_mary": (
            mary is not None
        ),
        "application_has_ecosystem": (
            ecosystem is not None
        ),
        "ecosystem_uses_application_mary": (
            ecosystem is not None
            and getattr(
                ecosystem,
                "mary",
                None,
            )
            is mary
        ),
        "exactly_one_mary_stage": (
            len(
                mary_stages
            )
            == 1
        ),
        "mary_stage_uses_application_mary": (
            len(
                mary_stages
            )
            == 1
            and getattr(
                mary_stages[0],
                "mary",
                None,
            )
            is mary
        ),
        "pipeline_uses_application_state": (
            pipeline is not None
            and getattr(
                pipeline,
                "runtime_state",
                None,
            )
            is state
        ),
    }

    failed = [
        name
        for name, passed in checks.items()
        if not passed
    ]

    return {
        "ok": not failed,
        "checks": checks,
        "failed": failed,
        "mary_stage_count": len(
            mary_stages
        ),
    }


def require_application_integrity(
    application: Any,
) -> dict[str, Any]:
    """
    Return the integrity report or raise when composition is inconsistent.

    This is intended for startup/diagnostic boundaries where silently running
    with two Mary objects or a mismatched ecosystem would be unsafe.
    """

    report = application_integrity_report(
        application
    )

    if not report["ok"]:
        failed = ", ".join(
            report["failed"]
        )

        raise RuntimeError(
            "MaryApplication composition integrity failed: "
            f"{failed}"
        )

    return report
