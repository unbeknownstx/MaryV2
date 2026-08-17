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
