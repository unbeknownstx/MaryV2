# MaryV2 12.12 Test Results

Package working tree verification completed before packaging.

## Canonical Python suite

```text
754 passed, 1 skipped
```

Command:

```text
python -m pytest tests test_breakthrough_11.py test_breakthrough_12.py -q
```

## Deterministic / offline release gate

```text
729 passed, 1 skipped
Diagnostics: 54 / 54 PASS
Healthy: True
Release verification PASSED
```

Registered milestone verifiers include the retained 12.7–12.11 surfaces plus:

```text
cognitive_character_runtime_12_12  PASS
```

Release hygiene, persistence recovery/state integrity, standalone readiness and
local tool-safety smoke all passed.

## 12.12 targeted features

Verified locally/deterministically:

- Cognitive Reservoir FTS5 retrieval + provenance
- SQLite reservoir cross-thread desktop-worker access
- reservoir persistence isolation with temporary application state
- deterministic local dialogue/reflex policy
- deterministic character-behavior utility layer
- Expression Director / provider-independent DeliveryPlan
- delivery-plan integration into TTS settings
- delivery-plan integration into VRM motion code
- purpose-specific local Ollama conversation model routing
- local model candidate catalog/benchmark harness
- Local Mind desktop workspace
- canonical setup references only existing test files
- 12.11.1/12.11.2 boot-resilience compatibility

## Frontend

Node syntax checks pass for:

- `desktop/src/main.js`
- `desktop/src/launcher.js`
- `desktop/src/runtime/turnTrace.js`
- `desktop/src/ui/presenceHome.js`
- `desktop/vite.config.js`

The packaging environment does not have the npm dependency tree available, so a
production Vite bundle is **not claimed here**. `SETUP_WINDOWS.ps1` runs `npm ci`,
`npm run check`, and `npm run build` on the target Windows PC and stops on any
failure.

## Live checks still required on the real PC

- local reflex perceived latency (`hey mary`)
- reservoir known-fact latency
- warm open-conversation latency
- local model benchmark/character-quality comparison
- ElevenLabs/VRM dynamic-expression feel
- production Vite build on Windows
