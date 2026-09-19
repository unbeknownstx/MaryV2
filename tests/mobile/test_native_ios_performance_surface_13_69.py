from __future__ import annotations

from pathlib import Path


ROOT = Path(__file__).resolve().parents[2]


def test_native_ios_consumes_canonical_performance_packet():
    models = (ROOT / "ios" / "MaryV2iOS" / "Sources" / "Models.swift").read_text(encoding="utf-8")
    state = (ROOT / "ios" / "MaryV2iOS" / "Sources" / "AppState.swift").read_text(encoding="utf-8")
    stage = (ROOT / "ios" / "MaryV2iOS" / "Sources" / "MaryStageView.swift").read_text(encoding="utf-8")

    assert "var performancePacket" in models
    assert 'displayHints["performance_packet"]' in models
    assert "applyTurnPresentation(result)" in state
    assert "lastPerformancePacket" in state
    assert "presentationExpression" in state
    assert "presentationGaze" in state
    assert "presentationHeadStyle" in state
    assert "deliveryPlan: result.deliveryPlan" in state
    assert "presentationExpression" in stage
    assert "presentationGaze" in stage
    assert "presentationHeadStyle" in stage
    assert "Presence linked" in stage


def test_native_ios_voice_receives_same_delivery_plan_as_stage():
    state = (ROOT / "ios" / "MaryV2iOS" / "Sources" / "AppState.swift").read_text(encoding="utf-8")

    assert "deliveryPlan: [String: Any] = [:]" in state
    assert "deliveryPlan: deliveryPlan" in state
