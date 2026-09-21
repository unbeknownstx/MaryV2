from pathlib import Path


ROOT = Path(__file__).resolve().parents[2]


def _text(relative: str) -> str:
    return (ROOT / relative).read_text(encoding="utf-8")


def test_revision_decision_history_is_visible_across_creator_surfaces():
    desktop = _text("desktop/src/main.js")
    pwa = _text("mobile_web/app.js")
    legacy = _text("mobile_native/MaryMobile/www/app.js")
    iphone = _text("ios/MaryV2iOS/Sources/WorkspaceDetailView.swift")

    assert "revision_review_history" in desktop
    assert "Creator revision decisions" in desktop
    assert "Recorded revision decisions" in desktop

    for source in (pwa, legacy):
        assert "revision_review_history" in source
        assert "CREATOR REVISION DECISIONS" in source
        assert "Revision decisions" in source
        assert "No creator revision decisions recorded yet." in source

    assert 'review["revision_review_history"]' in iphone
    assert 'Eyebrow(text: "Creator revision decisions")' in iphone
    assert 'DataRow(label: "Revision decisions"' in iphone
    assert "Evidence never decides automatically." in iphone


def test_revision_decision_surface_copy_preserves_authority_boundary():
    sources = [
        _text("desktop/src/main.js"),
        _text("mobile_web/app.js"),
        _text("mobile_native/MaryMobile/www/app.js"),
        _text("ios/MaryV2iOS/Sources/WorkspaceDetailView.swift"),
    ]
    combined = "\n".join(sources).lower()

    assert "revision decision" in combined
    assert "creator" in combined
    assert "never decides automatically" in combined or "approval never grants" in combined
    assert "automatic approval" not in combined
