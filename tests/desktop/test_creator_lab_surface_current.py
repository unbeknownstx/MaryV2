from pathlib import Path
from mary.desktop.bridge import _prepare_creator_image

def test_desktop_creator_image_preparation_is_bounded(tmp_path):
    from PySide6.QtGui import QImage
    source=tmp_path/"large.png"
    image=QImage(2600,1800,QImage.Format.Format_RGB32)
    image.fill(0xFF336699)
    assert image.save(str(source),"PNG")
    payload=_prepare_creator_image(str(source))
    assert payload.startswith(b"\xff\xd8")
    assert 0 < len(payload) <= 1_350_000

def test_desktop_creator_lab_uses_python_authority_boundary():
    root=Path(__file__).resolve().parents[2]
    js=(root/"desktop/src/main.js").read_text(encoding="utf-8")
    bridge=(root/"mary/desktop/bridge.py").read_text(encoding="utf-8")
    for name in ("chooseCreatorImage","describeCreatorImage","proposeCreatorSocial","speakCreatorDraft","creatorImageReady","creatorSocialReady","creatorDraftVoiceReady"):
        assert name in js
        assert name in bridge
    assert "perception.asset.register" in bridge
    assert "sensor.image_describe" in bridge
    assert "social.propose" in bridge
    assert "Authorization" not in js
    assert "Raw pixels are ephemeral task input" in js
