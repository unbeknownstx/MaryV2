"""
Tests for Mary's internal subsystem wiring integrity report.
"""

from mary.core.mary import Mary
from mary.runtime.subsystem_integrity import (
    require_subsystem_integrity,
    subsystem_integrity_report,
)


def test_subsystem_integrity_accepts_current_mary_graph(
    tmp_path,
    monkeypatch,
):
    monkeypatch.chdir(
        tmp_path
    )

    mary = Mary()

    report = subsystem_integrity_report(
        mary
    )

    assert report["ok"] is True
    assert report["failed"] == []
    assert report["checked"] >= 30
    assert all(
        report["groups"].values()
    )
    assert (
        require_subsystem_integrity(
            mary
        )
        is not None
    )


def test_subsystem_integrity_detects_turn_mind_split(
    tmp_path,
    monkeypatch,
):
    monkeypatch.chdir(
        tmp_path
    )

    mary = Mary()

    mary.turn_mind.knowledge = object()

    report = subsystem_integrity_report(
        mary
    )

    assert report["ok"] is False
    assert (
        report["checks"][
            "turn_mind.knowledge"
        ]
        is False
    )
    assert (
        "turn_mind.knowledge"
        in report["failed"]
    )


def test_subsystem_integrity_detects_realtime_perception_split(
    tmp_path,
    monkeypatch,
):
    monkeypatch.chdir(
        tmp_path
    )

    mary = Mary()

    mary.perception_director.attention = object()

    report = subsystem_integrity_report(
        mary
    )

    assert report["ok"] is False
    assert (
        report["checks"][
            "perception.realtime_attention"
        ]
        is False
    )
