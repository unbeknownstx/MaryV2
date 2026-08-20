# MaryV2 V2 Hard Test

Run from the activated Windows `.venv` in the MaryV2 root.

```powershell
python -m pytest tests -q
python -m scripts.run_diagnostics
python -m scripts.run_release_verification --offline
node --check desktop/src/main.js
```

Then test the persistent terminal:

```powershell
python -m scripts.run_mary
```

Use `/state`, `/resources`, `/last`, and `/pending` while talking to Mary.
Restart the process and verify selected durable memories/relationship state survive.

For deliberate failure testing, temporarily disable one provider at a time and
confirm free-first failover continues; disable internet and confirm Ollama-only
private/local operation remains available when Ollama is running. Do not enable
`MARY_RUN_OPENAI_TESTS` during ordinary verification.

For the desktop source build:

```powershell
cd desktop
npm ci
npm run build
cd ..
python -m scripts.run_desktop
```

For a Windows standalone folder after the source hard-test is green:

```powershell
powershell -ExecutionPolicy Bypass -File scripts\build_windows.ps1
```
