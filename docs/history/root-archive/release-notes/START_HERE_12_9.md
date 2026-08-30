# MaryV2 12.9 — Desktop Uplift + Runtime Instrumentation

This is an **overlay upgrade** for the proven MaryV2 12.8/12.8.2 Windows baseline.
It does not replace Mary's identity, memory, relationship state, provider abstraction,
VRM pipeline, or ecosystem ownership boundaries.

## What 12.9 adds

- measured provider/cognition/reflection/voice/desktop latency traces
- provider-attempt call timing without prompts or private-memory bodies
- live Runtime/Diagnostics workspace and right-rail turn summary
- micro/social response disposition with a 160-token ceiling
- tighter brief/medium completion budgets
- responsive 1366x768/smaller-laptop desktop breakpoints
- remembered windowed geometry via QSettings
- additive UI polish and a small frontend runtime module split
- deterministic-test isolation from the creator's live conversation route

## Safe install on the Windows canonical repo

1. Close Mary Desktop/Launcher.
2. Back up the repo and `%LOCALAPPDATA%\MaryV2\data` as you normally do.
3. Extract the supplied `MaryV2_12_9_Uplift_PATCH.zip`.
4. From the extracted patch folder, run:

```powershell
powershell -ExecutionPolicy Bypass -File .\INSTALL_12_9.ps1 -Target "C:\Users\Melvin\Documents\GitHub\MaryV2"
```

The installer backs up every replaced file under the target repo before copying.
It **never copies or deletes `.env` or `data/`**.

5. In the target repo run:

```powershell
.\.venv\Scripts\Activate.ps1
cd desktop
npm ci
npm run check
npm run build
cd ..
python -m pytest -q
python -m scripts.verify_uplift_12_9
```

6. Launch:

```powershell
powershell -ExecutionPolicy Bypass -File scripts\launch_windows.ps1
```

Open **Runtime** in the left navigation after a turn to inspect the measured trace.
