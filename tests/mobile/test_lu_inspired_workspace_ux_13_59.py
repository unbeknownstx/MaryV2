from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
WEB = ROOT / "mobile_web"
NATIVE = ROOT / "mobile_native" / "MaryMobile" / "www"


def test_quick_switcher_is_presentation_only_and_bundles_match():
    web = (WEB / "ux-13-59.js").read_text(encoding="utf-8")
    native = (NATIVE / "ux-13-59.js").read_text(encoding="utf-8")
    assert web == native
    assert "data-open" in web
    assert "workspace-sheet" in web
    assert "metaKey" in web and "ctrlKey" in web
    assert "fetch(" not in web
    assert "/api/" not in web
    assert "localStorage" not in web


def test_experience_loader_and_offline_shell_include_quick_switcher():
    for root in (WEB, NATIVE):
        experience = (root / "experience.js").read_text(encoding="utf-8")
        worker = (root / "sw.js").read_text(encoding="utf-8")
        assert "./ux-13-59.js" in experience
        assert "/ux-13-59.js" in worker
    assert (WEB / "experience.js").read_bytes() == (NATIVE / "experience.js").read_bytes()
    assert (WEB / "sw.js").read_bytes() == (NATIVE / "sw.js").read_bytes()
