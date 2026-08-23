# MaryV2 12.9 canonical Windows project

Canonical path: `C:\Users\Melvin\Documents\GitHub\MaryV2`

If this project is already at that path, do **not** run a migration step. Preserve the existing `.env` and `data/`.

Run:

```powershell
cd C:\Users\Melvin\Documents\GitHub\MaryV2
powershell -ExecutionPolicy Bypass -File .\SETUP_WINDOWS_12_9.ps1
```

Then launch:

```powershell
powershell -ExecutionPolicy Bypass -File .\scripts\launch_windows.ps1
```

The 12.9 targeted regression suite consists of the desktop uplift and provider-timing tests. Voice timing is covered by the desktop uplift verifier/runtime instrumentation rather than a nonexistent standalone `test_voice_timing_12_9.py` file.
