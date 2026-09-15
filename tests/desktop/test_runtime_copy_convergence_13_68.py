from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]


def test_generated_desktop_retires_fixed_groq_product_claim():
    vite = (ROOT / "desktop" / "vite.config.js").read_text(encoding="utf-8")
    assert "Fast chat model</span><strong>Groq · llama-3.1-8b-instant" in vite
    assert "Conversation route</span><strong>Automatic · see live Runtime route" in vite


def test_generated_desktop_retires_old_stage_delivery_copy():
    vite = (ROOT / "desktop" / "vite.config.js").read_text(encoding="utf-8")
    assert "12.12.2 keeps ordinary delivery restrained." in vite
    assert "Current delivery stays restrained and follows the live performance context." in vite
