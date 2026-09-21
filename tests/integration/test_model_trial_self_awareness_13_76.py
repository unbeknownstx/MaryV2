from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]


def _text(path: str) -> str:
    return (ROOT / path).read_text(encoding="utf-8")


def test_13_76_trial_lineage_becomes_bounded_self_evidence_without_output_retention():
    ledger = _text("mary/learning/model_experiments.py")
    introspection = _text("mary/cognition/self_introspection.py")
    fabric = _text("mary/runtime/system_fabric.py")

    assert "def _trial_evidence(" in ledger
    assert '"generated_output_retained": False' in ledger
    assert '"prompt_retained": False' in ledger
    assert '"quality_verified": False' in ledger
    assert '"trial_outcomes": trial_outcomes' in ledger
    assert '"completed_trials": completed_trials' in ledger

    assert 'trial_evidence = (' in introspection
    assert '"creator-reviewed comparison of completed bounded trial results' in introspection
    assert '"a completed bounded trial on the exact authorized experiment node' in introspection
    assert '"quality_verified": False' in introspection
    assert '"production_authority": False' in introspection

    assert '"trial_evidence": {' in fabric
    assert '"completed_trials": int(snapshot.get("completed_trials", 0) or 0)' in fabric
    assert '"quality_verified": False' in fabric


def test_13_76_trial_evidence_is_visible_on_all_active_product_surfaces():
    desktop = _text("desktop/src/main.js")
    web = _text("mobile_web/app.js")
    native = _text("mobile_native/MaryMobile/www/app.js")
    iphone = _text("ios/MaryV2iOS/Sources/WorkspaceDetailView.swift")

    assert web == native
    for source in (desktop, web, iphone):
        assert "Recorded trial outcomes" in source
        assert "Completed bounded trials" in source

    assert "experiments.trial_outcomes" in desktop
    assert "experiments.completed_trials" in desktop
    assert "experiments.trial_outcomes" in web
    assert "experiments.completed_trials" in web
    assert 'experiments["trial_outcomes"]' in iphone
    assert 'experiments["completed_trials"]' in iphone


def test_13_76_trial_evidence_does_not_claim_quality_or_promotion():
    ledger = _text("mary/learning/model_experiments.py")
    introspection = _text("mary/cognition/self_introspection.py")
    fabric = _text("mary/runtime/system_fabric.py")

    assert '"quality_verified": False' in ledger
    assert '"promotion_performed": False' in ledger
    assert '"automatic_promotion": False' in introspection
    assert '"production_authority": False' in introspection
    assert '"promotion_performed": False' in fabric
