from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]


def test_removed_command_palette_button_cannot_abort_frontend_boot():
    js = (ROOT / 'desktop' / 'src' / 'main.js').read_text(encoding='utf-8')
    html = (ROOT / 'desktop' / 'index.html').read_text(encoding='utf-8')
    assert 'id="command-palette-button"' not in html
    assert "$('#command-palette-button')?.addEventListener('click', openCommandPalette);" in js


def test_boot_has_defensive_watchdog_after_bridge_connection():
    js = (ROOT / 'desktop' / 'src' / 'main.js').read_text(encoding='utf-8')
    assert "setConnected(true, 'Connection: Strong');" in js
    assert "window.setTimeout(() => {" in js
    assert "finishBoot('Mary is ready.');" in js
    assert '}, 5000);' in js


def test_command_palette_keyboard_path_remains_guarded_and_available():
    js = (ROOT / 'desktop' / 'src' / 'main.js').read_text(encoding='utf-8')
    assert 'if (!commandPalette || !commandInput || !commandResults) return;' in js
    assert "event.key.toLowerCase() === 'k'" in js
    assert 'openCommandPalette();' in js
