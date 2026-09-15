from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]


def _text(path: str) -> str:
    return (ROOT / path).read_text(encoding="utf-8")


def test_13_67_product_layer_is_injected_after_historical_public_layers():
    vite = _text("desktop/vite.config.js")
    polish = vite.index("polish-13-7.css")
    relational = vite.index("relational-13-8.css")
    current = vite.index("product-shell-13-67.css")
    assert polish < relational < current
    assert "replaceAll('12.12', '13.67')" in vite
    assert "replaceAll('13.7', '13.67')" in vite
    assert "replaceAll('13.8', '13.67')" in vite


def test_13_67_clears_legacy_game_hud_without_removing_functional_nodes():
    css = _text("desktop/public/product-shell-13-67.css")
    html = _text("desktop/index.html")
    assert ".app-shell::after" in css
    assert "display: none !important" in css
    assert ".main-stage::before" in css
    assert "background: none !important" in css
    assert ".avatar-hud" in css
    assert 'id="avatar-canvas"' in html
    assert 'id="workspace-overlay"' in html
    assert 'id="messages"' in html


def test_13_67_makes_fallback_art_deterministic_and_keeps_live_vrm():
    css = _text("desktop/public/product-shell-13-67.css")
    main = _text("desktop/src/main.js")
    assert ".avatar-fallback .fallback-art.art-a" in css
    assert ".avatar-fallback .fallback-art.art-b" in css
    assert "opacity: .92 !important" in css
    assert "MaryCosma.vrm" in main
    assert "loadMaryVrm" in main


def test_13_67_keeps_conversation_and_mary_as_primary_stage():
    css = _text("desktop/public/product-shell-13-67.css")
    assert "width: calc(46% - 20px) !important" in css
    assert "inset: 0 0 0 49% !important" in css
    assert "background: var(--mary67-surface) !important" in css
    assert ".system-rail" in css
    assert ".system-rail-item.core strong" in css
    assert ".system-rail-item.compute strong" in css
    assert ".system-rail-item.voice strong" in css
    assert ".system-rail-item.presence strong" in css


def test_13_67_unifies_workspace_visual_grammar():
    css = _text("desktop/public/product-shell-13-67.css")
    for selector in (
        ".workspace-overlay",
        ".workspace-header",
        ".workspace-body",
        ".workspace-grid.three",
        ".workspace-panel",
        ".workspace-panel.accent",
        ".data-row",
        ".metric-card",
        ".game-card",
    ):
        assert selector in css
    assert "backdrop-filter: none !important" in css


def test_13_67_preserves_accessibility_and_reduced_motion():
    css = _text("desktop/public/product-shell-13-67.css")
    assert ":focus-visible" in css
    assert "prefers-contrast: more" in css
    assert "prefers-reduced-motion: reduce" in css
    assert "outline: 2px solid var(--mary67-focus)" in css


def test_13_67_responsive_policy_hides_context_before_talk():
    css = _text("desktop/public/product-shell-13-67.css")
    assert "@media (max-width: 1160px)" in css
    assert ".inspector-column" in css
    assert "display: none !important" in css
    assert "@media (max-width: 980px)" in css
    assert "grid-template-columns: 72px minmax(0, 1fr)" in css


def test_13_67_launcher_matches_desktop_product_language():
    css = _text("desktop/src/launcher.css")
    html = _text("desktop/launcher.html")
    assert "13.67 launcher product polish" in css
    assert "cursor: default !important" in css
    assert "background: #0d1121 !important" in css
    assert "PERSISTENT COMPANION · DESKTOP" in html
    assert "PLAY MARY" in html
    assert "presence-presentation" in html
