# MaryV2 macOS Desktop frontend boot fix

Target repository baseline: `bd8e0371c828d3627736b816f73543d1cb320145`.

## What this fixes

The canonical Mary Core connection is already working from the Mac. The desktop
window stalls on `Initializing Mary…` because current macOS Qt WebEngine /
Chromium treats the Vite production shell loaded from `file://` as a unique
origin and rejects Mary's neighboring JavaScript/CSS module files.

This patch keeps the existing local-file desktop architecture (including the
existing staged local voice-audio transport) and configures Qt WebEngine with
Chromium's narrow `--allow-file-access-from-files` compatibility switch before
any Qt WebEngine classes are imported. It does **not** use
`--disable-web-security`.

The compatibility flag is applied only on macOS. Windows/Linux behavior is
left unchanged. Existing `QTWEBENGINE_CHROMIUM_FLAGS` values are preserved.
The launcher gets the same fix because it is built by the same Vite pipeline.

## Files to copy over the MaryV2 repo root

- `mary/desktop/webengine_bootstrap.py` — new file
- `scripts/run_desktop.py` — replace existing
- `scripts/run_launcher.py` — replace existing
- `tests/desktop/test_webengine_bootstrap_macos.py` — new regression test

No `.env`, `data/`, memory/state, character sources, provider keys, Railway
configuration, or desktop UI source files are replaced.

## Verify after copying

From the MaryV2 repo root with `.venv` active:

```bash
python -m pytest -q tests/desktop/test_webengine_bootstrap_macos.py
```

Expected:

```text
4 passed
```

Then launch normally:

```bash
bash scripts/launch_macos.sh
```

You should not need the remote-debugging environment variables for normal use.

## Validation performed on this patch

- Python syntax/compile check: PASS
- New macOS WebEngine bootstrap regression tests: 4 passed
- Existing desktop source/boot/UI regression subset: 53 passed
- Total tests run for this patch package: 57 passed

A true visual Qt/macOS smoke test still has to run on the Mac itself because the
patch was prepared outside the Mac GUI environment.
