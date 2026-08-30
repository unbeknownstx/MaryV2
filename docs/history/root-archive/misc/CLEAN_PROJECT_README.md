# MaryV2 12.9 Clean Project

This is the complete clean MaryV2 12.9 source package reconstructed from the authoritative uploaded MaryV2 project plus the tested 12.9 Desktop Uplift + Runtime Instrumentation work.

It intentionally does **not** include private/runtime-local material from the creator's machine:

- `.env`
- `data/`
- `.git/`
- `.venv/`
- `desktop/node_modules/`
- generated caches
- installer `payload/`
- repository-local `upgrade_backups/`

The MaryCosma VRM and project-owned desktop/design/public assets are included.

## Recommended Windows recovery path

Do not repair the old working tree further. Extract this entire folder as a new sibling project, for example:

`C:\Users\Melvin\Documents\GitHub\MaryV2_12_9_CLEAN`

Then:

```powershell
cd C:\Users\Melvin\Documents\GitHub\MaryV2_12_9_CLEAN
powershell -ExecutionPolicy Bypass -File .\MIGRATE_PRIVATE_STATE.ps1
powershell -ExecutionPolicy Bypass -File .\SETUP_CLEAN_WINDOWS.ps1
```

`MIGRATE_PRIVATE_STATE.ps1` defaults to reading the old project from:

`C:\Users\Melvin\Documents\GitHub\MaryV2`

It copies only `.env` and `data/`. Use `-IncludeGitMetadata` only if you deliberately want the old `.git` history/remote metadata copied into the clean folder.

The setup script creates a new `.venv`, installs Python dependencies, performs `npm ci`, frontend syntax/build checks, the 12.9 targeted tests, the full canonical pytest suite, the offline release gate, and state-integrity verification.

## Important

Keep the old MaryV2 folder untouched until this clean project launches and your memory/continuity state is visibly correct. Once validated, the old folder can be archived and this clean folder can become the canonical working copy.
