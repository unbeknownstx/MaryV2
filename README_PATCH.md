# MaryV2 Mac Desktop Loopback Fix — 2026-09-01

This replaces the earlier Chromium-flag workaround with a structural desktop fix.

## What the observed stall means

The native Qt window itself is launching, and its static HTML/CSS splash is visible. The boot text never advances beyond `Initializing Mary…`, which means the Vite JavaScript module has not executed its first `bootStep(28, 'Loading character renderer…')` call.

The DevTools errors captured on the Mac showed the built Vite chunks being blocked under a `file://` / null origin. The canonical Mary Core was independently verified from the Mac and is not the failing component.

## What this patch changes

Mary Desktop and Mary Launcher now serve the existing `desktop/dist` build through a temporary **127.0.0.1-only** HTTP server on an ephemeral port instead of opening `index.html` through `file://`.

That gives Vite's ES modules, CSS, manifest, VRM model and static assets one normal same-origin browser origin. It does **not** create another Mary runtime or expose the UI to the LAN.

Desktop voice audio is also mapped through the same loopback origin so the change does not trade the boot fix for an HTTP-to-file audio restriction.

The local presentation server shuts down when the native window closes.

## Files to copy over MaryV2

Copy the following folders from this package over the MaryV2 project root and choose Merge/Replace:

- `mary/desktop/static_server.py` (new)
- `mary/desktop/audio_cache.py`
- `mary/desktop/window.py`
- `mary/launcher/window.py`
- `scripts/run_desktop.py`
- `scripts/run_launcher.py`
- `tests/desktop/test_loopback_static_server_macos.py` (new regression tests)

The two `scripts/run_*.py` files intentionally restore the normal launch entrypoints, so the previous `QTWEBENGINE_CHROMIUM_FLAGS` bootstrap workaround is no longer needed. If `mary/desktop/webengine_bootstrap.py` exists from the earlier patch, it may remain; nothing imports it after these files are copied.

## Validation performed against the supplied MaryV2 project

- Python syntax compilation: PASS
- New loopback/static/audio regression tests: PASS
- Existing desktop test suite plus new tests: **111 passed**

## First Mac verification

From the MaryV2 root with `.venv` active:

```bash
bash scripts/launch_macos.sh
```

No Qt debug flags are required.

If the splash advances from `Initializing Mary…` to `Loading character renderer…` or `Connected to Mary core…`, the original file-origin boot failure is gone.
