from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]


def _text(path: str) -> str:
    return (ROOT / path).read_text(encoding="utf-8")


def test_desktop_product_shell_is_installed_last():
    source = _text("desktop/src/main.js")
    assert "import './product-shell-13-66.css';" in source
    assert source.index("import './experience-v2.css';") < source.index("import './product-shell-13-66.css';")


def test_primary_desktop_shell_has_human_facing_system_projection():
    html = _text("desktop/index.html")
    for element_id in (
        "shell-core-state",
        "shell-compute-state",
        "shell-voice-state",
        "shell-presence-state",
        "system-core-value",
        "system-compute-value",
        "system-voice-value",
        "system-nodes-value",
    ):
        assert f'id="{element_id}"' in html

    assert "PERSISTENT PRESENCE" in html
    assert "WORK & CREATE" in html
    assert "PRESENCE" in html
    assert "FABRIC" in html


def test_product_shell_reduces_transparency_and_prioritizes_talk():
    css = _text("desktop/src/product-shell-13-66.css")
    assert "--shell-panel: #0c1020" in css
    assert "backdrop-filter: none !important" in css
    assert ".chat-card" in css
    assert "background: #0d1122 !important" in css
    assert ".avatar-stage" in css
    assert "inset: 0 0 0 50%" in css
    assert ".system-rail" in css
    assert ".nav-section-label" in css


def test_product_shell_projects_new_compute_fabric_without_taking_authority():
    source = _text("desktop/src/main.js")
    assert "function projectProductShell()" in source
    assert "dashboardState?.compute_fabric" in source
    assert "capabilities['llm.local']" in source
    assert "local_device: 'Local Model'" in source
    assert "canonical Mary Core".lower() in source.lower()


def test_runtime_workspace_exposes_unified_model_compute_fabric():
    source = _text("desktop/src/main.js")
    assert "MODEL & COMPUTE FABRIC" in source
    assert "Conversation Route" in source
    assert "Local Compute" in source
    assert "Execution Portfolio" in source
    assert "LM Studio, Ollama, llama.cpp" in source


def test_launcher_matches_current_product_shell():
    html = _text("desktop/launcher.html")
    css = _text("desktop/src/launcher.css")
    assert "PERSISTENT COMPANION · DESKTOP" in html
    assert "launcher-capabilities" in html
    assert "Persistent Mary" in html
    assert "Local + cloud" in html
    assert "background:#0d1121" in css
    assert "backdrop-filter:none" in css


def test_final_public_css_cascade_preserves_13_66_clarity():
    polish = _text("desktop/public/polish-13-7.css")
    relational = _text("desktop/public/relational-13-8.css")
    assert "13.66 final-cascade convergence" in polish
    assert "backdrop-filter: none !important" in polish
    assert ".inspector-column { display:block; }" in polish
    assert "background: #11162a" in relational
    assert "backdrop-filter: none" in relational
