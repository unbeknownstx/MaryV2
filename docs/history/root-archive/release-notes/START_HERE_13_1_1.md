# START HERE — MaryV2 13.1.1

This is the consolidated baseline built from the creator's newest Windows project plus all 13.0/13.1 realtime/development/mobile additions.

## Overlay safety

The release overlay intentionally excludes `.env`, `data/`, credentials, private memories, relationship/developed-self state, Voice Lab private IDs, response-feedback data, `.git`, `.venv`, `node_modules`, caches, and runtime reports.

Before overlaying, keep the pre-13.1.1 `.env` + `data/` backup already created on the Windows PC.

After overlay:

```powershell
python -m scripts.check_mary_13_1
powershell -ExecutionPolicy Bypass -File .\scripts\test_fast.ps1
```

If fast checks pass, continue with:

```powershell
powershell -ExecutionPolicy Bypass -File .\scripts\test_full.ps1
powershell -ExecutionPolicy Bypass -File .\scripts\test_release.ps1
```

Do not rebuild vectors until Mary launches with the preserved canonical state and routing. Then inspect vector status with:

```powershell
python -m scripts.rebuild_semantic_vectors --status
```

For desktop host build:

```powershell
cd desktop
npm ci
npm run check
npm run build
cd ..
```

Then test terminal/desktop/mobile before committing through GitHub Desktop.
