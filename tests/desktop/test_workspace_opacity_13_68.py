from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]


def test_non_talk_workspaces_hide_chat_and_composer():
    css = (ROOT / "desktop" / "public" / "product-shell-13-68.css").read_text(encoding="utf-8")
    assert '.app-shell:not([data-screen="chat"]) .chat-card' in css
    assert '.app-shell:not([data-screen="chat"]) .composer-deck' in css
    assert 'display: none !important' in css
    assert 'grid-template-rows: 52px minmax(0, 1fr) !important' in css


def test_workspace_surface_is_explicitly_opaque_and_unblurred():
    css = (ROOT / "desktop" / "public" / "product-shell-13-68.css").read_text(encoding="utf-8")
    assert '.workspace-overlay {' in css
    assert 'background: #090d1c !important' in css
    assert 'opacity: 1 !important' in css
    assert 'backdrop-filter: none !important' in css
