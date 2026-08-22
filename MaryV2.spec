# -*- mode: python ; coding: utf-8 -*-
from pathlib import Path
import sys

ROOT = Path(SPEC).resolve().parent
ENV_EXAMPLE = ROOT / ".env.example"
ICON = ROOT / "desktop" / "public" / "assets" / "mary_icon.ico"
if not ENV_EXAMPLE.exists():
    ENV_EXAMPLE = ROOT / "example.env.example"

analysis = Analysis(
    [str(ROOT / "scripts" / "run_desktop.py")],
    pathex=[str(ROOT)],
    binaries=[],
    datas=[
        (str(ROOT / "desktop" / "dist"), "desktop/dist"),
        (str(ENV_EXAMPLE), "."),
    ],
    hiddenimports=[],
    hookspath=[],
    hooksconfig={},
    runtime_hooks=[],
    excludes=["PyQt5", "PyQt6", "PySide2"],
    noarchive=False,
    optimize=1,
)
pyz = PYZ(analysis.pure)
exe = EXE(
    pyz,
    analysis.scripts,
    [],
    exclude_binaries=True,
    name="MaryV2",
    debug=False,
    bootloader_ignore_signals=False,
    strip=False,
    upx=False,
    console=False,
    icon=str(ICON) if sys.platform == "win32" and ICON.exists() else None,
    disable_windowed_traceback=False,
)
collection = COLLECT(
    exe,
    analysis.binaries,
    analysis.datas,
    strip=False,
    upx=False,
    name="MaryV2",
)


# PyInstaller uses COLLECT for Windows/Linux. On macOS, wrap the same
# verified runtime in a native .app bundle so Mary can launch like an app.
if sys.platform == "darwin":
    bundle = BUNDLE(
        collection,
        name="MaryV2.app",
        icon=None,
        bundle_identifier="com.unbe.maryv2",
    )
