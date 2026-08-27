"""
Tests for the MaryApplication ONE-MARY composition integrity checks.
"""

from mary.core.mary import Mary
from mary.ecosystem import MaryEcosystem
from mary.runtime.application import create_application
from mary.runtime.integrity import (
    application_integrity_report,
    require_application_integrity,
)


def test_application_integrity_accepts_canonical_composition(
    tmp_path,
    monkeypatch,
):
    monkeypatch.chdir(
        tmp_path
    )

    mary = Mary()

    app = create_application(
        mary=mary,
        memory_path=(
            tmp_path
            / "memory"
            / "memory.json"
        ),
    )

    report = application_integrity_report(
        app
    )

    assert report["ok"] is True
    assert report["failed"] == []
    assert report["mary_stage_count"] == 1
    assert all(
        report["checks"].values()
    )

    assert (
        require_application_integrity(
            app
        )
        is not None
    )


def test_application_integrity_detects_second_ecosystem_mary(
    tmp_path,
    monkeypatch,
):
    monkeypatch.chdir(
        tmp_path
    )

    app = create_application(
        memory_path=(
            tmp_path
            / "memory"
            / "memory.json"
        ),
    )

    second_mary = Mary()
    app.ecosystem = MaryEcosystem(
        second_mary
    )

    report = application_integrity_report(
        app
    )

    assert report["ok"] is False
    assert (
        report["checks"][
            "ecosystem_uses_application_mary"
        ]
        is False
    )
    assert (
        "ecosystem_uses_application_mary"
        in report["failed"]
    )


def test_application_integrity_detects_pipeline_state_mismatch(
    tmp_path,
    monkeypatch,
):
    monkeypatch.chdir(
        tmp_path
    )

    app = create_application(
        memory_path=(
            tmp_path
            / "memory"
            / "memory.json"
        ),
    )

    app.pipeline.runtime_state = object()

    report = application_integrity_report(
        app
    )

    assert report["ok"] is False
    assert (
        report["checks"][
            "pipeline_uses_application_state"
        ]
        is False
    )
