# -*- mode: python ; coding: utf-8 -*-
from pathlib import Path
import sys

ROOT = Path(SPEC).resolve().parent
ICON = ROOT / "desktop" / "public" / "assets" / "mary_icon.ico"

analysis = Analysis(
    [str(ROOT / "scripts" / "run_launcher.py")],
    pathex=[str(ROOT)],
    binaries=[],
    datas=[
        (str(ROOT / "desktop" / "dist"), "desktop/dist"),
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
    name="MaryLauncher",
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
    name="MaryLauncher",
)

if sys.platform == "darwin":
    bundle = BUNDLE(
        collection,
        name="MaryLauncher.app",
        icon=None,
        bundle_identifier="com.unbe.maryv2.launcher",
    )
