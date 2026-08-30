# MaryV2 12.9 Clean Project — Verification Results

The clean project package was created from the authoritative uploaded MaryV2 baseline plus the tested 12.9 Desktop Uplift + Runtime Instrumentation implementation.

Validation performed on the clean tree before packaging:

- canonical full repository suite: **697 passed, 1 skipped**
- `scripts.verify_uplift_12_9`: **PASS**
- deterministic/offline release verification: **PASS**
- system diagnostics inside release gate: **54 / 54 PASS, Healthy True**
- frontend JavaScript syntax (`main.js`, `launcher.js`, `runtime/turnTrace.js`, `vite.config.js`): **PASS**
- release hygiene: **PASS** with no `.env` and no private `data/` in this clean source snapshot

The same 12.9 frontend source previously completed a real Windows Vite 8.2.1 production build on the target PC. This clean package deliberately excludes `desktop/node_modules/` and generated `desktop/dist/`; `SETUP_CLEAN_WINDOWS.ps1` rebuilds them natively on the target Windows host from `package-lock.json`.

A packaging replay is also performed after ZIP creation: the ZIP is extracted into a separate fresh directory and its canonical Python suite / 12.9 verifier are executed again.
