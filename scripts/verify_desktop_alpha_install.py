"""Verify MaryV2 Desktop Alpha files without requiring a display server."""

from __future__ import annotations

import json
from pathlib import Path


def main() -> int:
    root = Path(__file__).resolve().parents[1]
    required = [
        root / "requirements-desktop.txt",
        root / "mary" / "desktop" / "bridge.py",
        root / "mary" / "desktop" / "window.py",
        root / "mary" / "desktop" / "voice.py",
        root / "mary" / "voice" / "providers" / "elevenlabs.py",
        root / "desktop" / "package.json",
        root / "desktop" / "vite.config.js",
        root / "desktop" / "index.html",
        root / "desktop" / "src" / "main.js",
        root / "desktop" / "src" / "style.css",
        root / "scripts" / "run_desktop.py",
    ]

    print("MARYV2 DESKTOP ALPHA INSTALL VERIFICATION")
    print("=" * 72)

    missing = [path for path in required if not path.exists()]
    if missing:
        for path in missing:
            print(f"FAIL  missing {path.relative_to(root)}")
        return 1

    package = json.loads((root / "desktop" / "package.json").read_text(encoding="utf-8"))
    checks = [
        (package["dependencies"].get("three") == "0.185.1", "Three.js version pinned"),
        (package["dependencies"].get("@pixiv/three-vrm") == "3.5.5", "three-vrm version pinned"),
        ("MaryApplication" in (root / "mary" / "desktop" / "bridge.py").read_text(encoding="utf-8"), "desktop uses canonical MaryApplication"),
        ("base: './'" in (root / "desktop" / "vite.config.js").read_text(encoding="utf-8"), "Vite emits Qt-friendly relative asset paths"),
        ("VRMUtils.rotateVRM0(currentVrm)" in (root / "desktop" / "src" / "main.js").read_text(encoding="utf-8"), "VRM orientation is version-aware"),
        ("setNormalizedPose" in (root / "desktop" / "src" / "main.js").read_text(encoding="utf-8"), "desktop applies a relaxed humanoid pose"),
        ("currentVrm.scene.rotation.y = Math.PI" not in (root / "desktop" / "src" / "main.js").read_text(encoding="utf-8"), "VRM 1.0 is not forcibly turned backward"),
        ("new THREE.Clock" not in (root / "desktop" / "src" / "main.js").read_text(encoding="utf-8"), "deprecated Three.js Clock removed"),
        ("expression = mary.avatar.sync_emotion()" not in (root / "mary" / "desktop" / "bridge.py").read_text(encoding="utf-8"), "desktop bridge keeps AvatarState and AvatarExpression types separate"),
        ("leftUpperArm: { rotation: quaternionArrayFromEuler(0, 0, -1.28) }" in (root / "desktop" / "src" / "main.js").read_text(encoding="utf-8"), "left arm lowers from T-pose"),
        ("rightUpperArm: { rotation: quaternionArrayFromEuler(0, 0, 1.28) }" in (root / "desktop" / "src" / "main.js").read_text(encoding="utf-8"), "right arm lowers from T-pose"),
        ("Math.max(verticalDistance, horizontalDistance) * 1.18" in (root / "desktop" / "src" / "main.js").read_text(encoding="utf-8"), "camera frames Mary using full-body geometry"),
        ("worker.moveToThread(thread)" in (root / "mary" / "desktop" / "bridge.py").read_text(encoding="utf-8"), "desktop conversation uses a dedicated QThread"),
        ("@Slot(object)" in (root / "mary" / "desktop" / "bridge.py").read_text(encoding="utf-8"), "desktop completion is marshalled through a Qt slot"),
        ("Avatar presentation is best-effort" in (root / "mary" / "desktop" / "bridge.py").read_text(encoding="utf-8"), "avatar presentation cannot swallow a chat response"),
        ("Mary's desktop worker stopped without returning a response." in (root / "mary" / "desktop" / "bridge.py").read_text(encoding="utf-8"), "desktop releases Thinking on unexpected worker termination"),
        ("timeout=20.0" in (root / "mary" / "llm" / "providers" / "groq.py").read_text(encoding="utf-8"), "Groq interactive request timeout is bounded"),
        ("max_retries=0" in (root / "mary" / "llm" / "providers" / "groq.py").read_text(encoding="utf-8"), "Groq SDK retries do not trap desktop in Thinking"),
        ("MARY_TTS_PROVIDER" in (root / "mary" / "desktop" / "voice.py").read_text(encoding="utf-8"), "desktop voice is explicit opt-in"),
        ("voice=voice_payload" in (root / "mary" / "desktop" / "bridge.py").read_text(encoding="utf-8"), "desktop response carries synthesized voice separately from text"),
        ("playVoice(payload.voice || {})" in (root / "desktop" / "src" / "main.js").read_text(encoding="utf-8"), "desktop plays returned Mary voice audio"),
        ("PlaybackRequiresUserGesture" in (root / "mary" / "desktop" / "window.py").read_text(encoding="utf-8"), "Qt permits async TTS playback"),
        ("Voice synthesis is also best-effort" in (root / "mary" / "desktop" / "bridge.py").read_text(encoding="utf-8"), "voice failure cannot swallow Mary's text response"),
    ]

    failed = False
    for ok, label in checks:
        print(("PASS" if ok else "FAIL") + f"  {label}")
        failed = failed or not ok

    if failed:
        return 1

    dist = root / "desktop" / "dist" / "index.html"
    if dist.exists():
        print("PASS  desktop frontend is built")
    else:
        print("INFO  frontend not built yet; run `cd desktop`, `npm install`, `npm run build`")

    print("=" * 72)
    print("DESKTOP ALPHA FILES INSTALLED CORRECTLY")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
