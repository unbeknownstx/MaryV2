from pathlib import Path
import re

ROOT = Path(__file__).resolve().parents[2]


def test_static_dom_event_bindings_are_null_safe():
    js = (ROOT / 'desktop' / 'src' / 'main.js').read_text(encoding='utf-8')
    # Direct static querySelector bindings at module scope must not be able to
    # abort the entire ES module when a presentation control is removed.
    unsafe = re.findall(r"\$\('[^']+'\)\.addEventListener", js)
    assert unsafe == []


def test_cached_optional_dom_controls_use_optional_event_binding():
    js = (ROOT / 'desktop' / 'src' / 'main.js').read_text(encoding='utf-8')
    for name in ('composer', 'input', 'micButton', 'musicPlayButton', 'musicAudio', 'commandInput', 'screenLauncher'):
        assert f"{name}.addEventListener" not in js


def test_frontend_installs_detailed_boot_error_diagnostic():
    js = (ROOT / 'desktop' / 'src' / 'main.js').read_text(encoding='utf-8')
    assert "window.addEventListener('error'" in js
    assert '[MaryUI]' in js
    assert 'event.filename' in js
    assert 'event.lineno' in js
    assert 'event.colno' in js


def test_essential_boot_dom_contract_is_present():
    html = (ROOT / 'desktop' / 'index.html').read_text(encoding='utf-8')
    essential = {
        'app', 'avatar-canvas', 'composer', 'message-input', 'send-button',
        'mic-button', 'workspace-overlay', 'workspace-body', 'command-palette',
        'command-input', 'command-results', 'music-audio', 'music-play-button',
        'screen-launcher', 'titlebar', 'window-minimize', 'window-maximize',
        'window-close', 'boot-screen', 'boot-status', 'boot-progress-bar',
    }
    for dom_id in essential:
        assert f'id="{dom_id}"' in html, dom_id
