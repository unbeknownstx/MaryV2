from pathlib import Path


ROOT = Path(__file__).resolve().parents[2]


def test_current_readme_is_product_entrypoint_not_old_sourcebook_patch_note():
    text = (ROOT / "README.md").read_text(encoding="utf-8")
    assert "Many surfaces. Many capability nodes. One persistent Mary." in text
    assert "MARY_ROOT.md" in text
    assert "SYSTEM_REGISTRY.md" in text
    assert "Copy/merge the `character_sources/active/` directory" not in text


def test_13_7_documentation_and_visual_contracts_exist():
    assert (ROOT / "docs" / "README.md").is_file()
    assert (ROOT / "docs" / "architecture" / "PRODUCT_EXPERIENCE_13_7.md").is_file()
    assert (ROOT / "docs" / "design" / "MARY_VISUAL_SYSTEM.md").is_file()
    root_contract = (ROOT / "MARY_ROOT.md").read_text(encoding="utf-8")
    assert "Graceful-degradation rule" in root_contract
    assert "Product experience rule" in root_contract


def test_desktop_build_loads_final_polish_layer_and_normalizes_historical_labels():
    vite = (ROOT / "desktop" / "vite.config.js").read_text(encoding="utf-8")
    css = (ROOT / "desktop" / "public" / "polish-13-7.css").read_text(encoding="utf-8")
    assert "polish-13-7.css" in vite
    assert "replaceAll('12.12', '13.7')" in vite
    assert "prefers-reduced-motion" in css
    assert "max-width: 1380px" in css
    assert "min-width: 960px" in css


def test_mobile_web_and_compatibility_wrapper_are_byte_aligned_for_shared_shell():
    web = ROOT / "mobile_web"
    compat = ROOT / "mobile_native" / "MaryMobile" / "www"
    for name in ("index.html", "polish-13-7.css", "sw.js"):
        assert (web / name).read_bytes() == (compat / name).read_bytes()
    index = (web / "index.html").read_text(encoding="utf-8")
    assert "PERSISTENT COMPANION SYSTEM · 13.7" in index
    assert "polish-13-7.css" in index
    service_worker = (web / "sw.js").read_text(encoding="utf-8")
    assert "maryv2-mobile-shell-v13-2-unified-v13-7-product-polish" in service_worker
    assert "'/polish-13-7.css'" in service_worker


def test_native_iphone_theme_has_shared_accessibility_and_touch_contracts():
    theme = (ROOT / "ios" / "MaryV2iOS" / "Sources" / "Theme.swift").read_text(encoding="utf-8")
    assert "accessibilityReduceMotion" in theme
    assert "minimumTouchTarget: CGFloat = 44" in theme
    assert "surfaceElevated" in theme
    assert "MaryTheme.bg" in theme


def test_stale_patch_status_files_are_not_active_root_instructions():
    for name in (
        "NEXT_MAC_STEPS.md",
        "PACKAGE_STATUS.txt",
        "README_PATCH.md",
        "TEST_RESULTS.txt",
        "SYNTHESIS_UPGRADE_2026-09-01.md",
    ):
        assert not (ROOT / name).exists(), name
    history_note = (ROOT / "docs" / "history" / "ROOT_CLEANUP_13_7.md").read_text(encoding="utf-8")
    assert "Git history" in history_note
