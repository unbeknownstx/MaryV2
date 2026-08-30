MARYV2 12.11.2 BOOT STABILITY HOTFIX

Purpose:
- Prevent optional/missing desktop controls from aborting frontend module boot.
- Make static startup event bindings null-safe.
- Add detailed JavaScript source/line diagnostics to the Qt PowerShell console.
- Preserve the 12.11 fast-dialogue, connected-presence, voice, YouTube, and WebSocket systems.

Safe to paste over the canonical MaryV2 root.
Does not include or modify .env or data/.

After copying:
  cd C:\Users\Melvin\Documents\GitHub\MaryV2\desktop
  npm run check
  npm run build
  cd ..
  python -m pytest tests\desktop\test_boot_resilience_12_11_1.py tests\desktop\test_boot_stability_12_11_2.py tests\desktop\test_js_console_diagnostics_12_11_2.py -q
  powershell -ExecutionPolicy Bypass -File .\scripts\launch_windows.ps1

Expected hotfix tests: 8 passed.
Full source validation used to build this hotfix: 734 passed, 1 skipped.
Offline release verification: PASS, diagnostics 54/54.
