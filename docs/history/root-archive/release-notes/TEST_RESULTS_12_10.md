# MaryV2 12.10 Verification Record

Release: **MaryV2 12.10.0 — Presence Fabric + Companion Home + Presentation Polish**

## Canonical Python suite

```text
python -m pytest tests test_breakthrough_11.py test_breakthrough_12.py -q
712 passed, 1 skipped
```

## Deterministic/offline release gate

```text
python -m scripts.run_release_verification --offline
687 passed, 1 skipped
54 / 54 diagnostics PASS
Healthy: True
Release verification PASSED
```

The gate includes every registered V2 milestone verifier, including 12.8 Ecosystem + Presence, 12.9 Desktop Uplift, and 12.10 Presence + Presentation.

## Frontend source verification

```text
npm run check
PASS
```

12.10 removes the old Vite `__dirname` configuration and uses `import.meta.dirname`. The Vite 8/Rolldown config also defines separate Three/VRM/vendor code-splitting groups. The packaging host cannot reinstall the npm dependency tree from the registry, so the final production bundle is intentionally rebuilt on the real Windows host by `SETUP_WINDOWS_12_10.ps1` using `npm ci`, `npm run check`, and `npm run build`. Setup stops if that build fails.

## State safety

All package verification uses sanitized or temporary state. The distributable excludes `.env`, private `data/`, `.git`, `.venv`, `node_modules`, generated `desktop/dist`, and caches. The existing canonical Desktop state under `%LOCALAPPDATA%\MaryV2\data` is not rewritten by this source package.
