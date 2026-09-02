# MaryV2 Cognitive Character Runtime — September 1, 2026 Verification

## Scope

This pass evolves the existing canonical MaryV2 architecture in place. It does not create a second Mary, second memory owner, second relationship owner, second autonomy executor, or client-local identity authority.

Primary additions in this convergence pass include:

- Core-owned Live Scene projection across desktop/mobile.
- Realtime speech-floor arbitration and high-rate data-plane contracts.
- bounded streaming-chat ingestion and presence coordination.
- Twitch EventSub and OBS WebSocket transport adapters.
- ephemeral World Context / World Pulse refresh path.
- Adapter Lab + reviewed external model/LoRA candidate catalog.
- platform-local model storage and verified fetch tooling.
- optional llama.cpp local/device inference path.
- cross-platform capability-node runner.
- contextual memory reranking without changing authority-bearing memory payloads.
- desktop/mobile surface convergence checks.

## Canonicality rules preserved

- Mary Core remains Mary.
- clients and compute nodes contribute observations/capabilities only.
- chat and perception are context, never creator authority.
- learned/model outputs do not directly mutate canonical identity or persistent state.
- local model weights are runtime assets outside the repository.
- derived indexes/rankings remain rebuildable and non-authoritative.

## Final deterministic verification

Executed from the upgraded source tree:

```text
python -m scripts.run_release_verification
```

Result:

```text
1570 passed, 1 skipped
Python compile: PASS
System diagnostics: 61 / 61 PASS
Warnings: 0
Failures: 0
Release hygiene: PASS
Standalone readiness: PASS
MaryV2 convergence: PASS
Repository structure: PASS
Local tool safety: PASS
Release verification: PASS
```

The release gate also re-proved memory restart, provider resilience, self-introspection, creator directives, relationship development, curiosity development, priority grounding, emotion appraisal, conversation continuity, performance, long-session hardening, mobile, distributed compute, hybrid retrieval, developed-self persistence, provider routing, task orchestration, bounded resources, persistence recovery, and legacy 12.x/13.x milestone compatibility.

## Frontend verification

Source-level JavaScript checks pass for the modified desktop/mobile sources and the native mobile web bundle is synchronized.

A fresh production `vite build` was **not executed in this build container** because the uploaded source snapshot intentionally contains no `node_modules` and this environment could not reach the npm registry reliably enough to reconstruct the locked frontend dependency tree. This does not weaken the deterministic Python/repository gate; the host build scripts explicitly rebuild frontend dependencies and the Vite production bundle before executable packaging.

On the Mac, run the normal host dependency/build sequence before packaging the app.

## Model assets

No neural model weights are included in this source tree or release package.

The repository contains only:

- reviewed candidate metadata;
- exact filenames/base-model compatibility where known;
- expected SHA-256 hashes where stable;
- license/source references;
- explicit download/bootstrap scripts.

Weights resolve to Mary platform-local model storage and are protected by `.gitignore` as a second line of defense.

## Operational conclusion

This source tree is a coherent green integration checkpoint. Future work should branch/evolve from this checkpoint and preserve the same rule: no feature is complete unless Core owns the canonical state, device/client surfaces consume the same projection, capability advertisements match executable capability truth, and the full deterministic release gate remains green.
