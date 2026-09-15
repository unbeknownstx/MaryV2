from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]


def _text(path: str) -> str:
    return (ROOT / path).read_text(encoding="utf-8")


def test_windows_desktop_launch_rebuilds_stale_vite_bundle():
    script = _text("scripts/launch_windows.ps1")
    assert '$DistIndex = Join-Path $DesktopRoot "dist\\index.html"' in script
    assert "$NeedsBuild = -not (Test-Path $DistIndex)" in script
    assert "LastWriteTimeUtc -gt $DistTime" in script
    assert 'Write-Host "MaryV2: rebuilding Desktop frontend..."' in script
    assert "& $Npm.Source run check" in script
    assert "& $Npm.Source run build" in script
    assert "-m scripts.run_desktop" in script


def test_windows_launcher_rebuilds_stale_vite_bundle_before_serving_dist():
    script = _text("scripts/launch_launcher_windows.ps1")
    assert '$DistIndex = Join-Path $DesktopRoot "dist\\index.html"' in script
    assert "$NeedsBuild = -not (Test-Path $DistIndex)" in script
    assert 'Join-Path $DesktopRoot "launcher.html"' in script
    assert "LastWriteTimeUtc -gt $DistTime" in script
    assert "& $Npm.Source run build" in script
    assert "-m scripts.run_launcher" in script


def test_windows_freshness_guard_bootstraps_vite_only_when_missing():
    for path in ("scripts/launch_windows.ps1", "scripts/launch_launcher_windows.ps1"):
        script = _text(path)
        assert 'node_modules\\.bin\\vite.cmd' in script
        assert "& $Npm.Source ci" in script
        assert "Desktop source changed but npm is not available" in script


def test_python_desktop_entrypoints_share_frontend_freshness_guard():
    helper = _text("mary/desktop/frontend_build.py")
    desktop_window = _text("mary/desktop/window.py")
    launcher_window = _text("mary/launcher/window.py")

    assert "def frontend_needs_build" in helper
    assert "def ensure_desktop_frontend" in helper
    assert 'subprocess.run([npm, "run", "check"]' in helper
    assert 'subprocess.run([npm, "run", "build"]' in helper
    assert 'ensure_desktop_frontend(project_root, page="index.html")' in desktop_window
    assert 'ensure_desktop_frontend(root, page="launcher.html")' in launcher_window
