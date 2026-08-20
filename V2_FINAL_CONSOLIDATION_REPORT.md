# MaryV2 V2 Breakthrough 12 — Host Awareness + Dynamic Capability Resolution

Breakthrough 12 builds on the fully verified Breakthrough 11 system without replacing Mary's working identity, memory, relationship, cognition, agency, emotion, orchestration, or provider architecture.

## New architectural boundary

Mary now owns one process-local `RuntimeEnvironment` capability resolver. It does not own character state. It reports the current host/platform, provider availability, display-safe host capabilities, preferred provider policies, and effective provider routes for the current machine.

Ollama remains an optional provider. On a Windows/macOS/Linux host where Ollama is reachable, personal conversation can remain Ollama-first. On Replit, Codespaces, or another host where Ollama is unavailable, Mary keeps the same preferred policy but removes unavailable providers from the effective route and continues through configured cloud providers.

Runtime/environment questions are resolved from Mary's own process state before current-information web heuristics. Phrases such as `what models can u use right now?` and `does anything change because were not on my pc?` therefore stay local, while genuinely external current questions such as `what is the latest Python release?` still use the intentional web-approval path.

## New terminal visibility

`/route` now distinguishes preferred policy from effective host route and reports provider availability. `/environment` (also `/env` or `/capabilities`) shows the display-safe host/capability snapshot.

## Verification

- Breakthrough 12 focused regressions: **12 passed**
- Current deterministic suite: **565 passed, 1 skipped**
- Diagnostics: **54 / 54 PASS**
- Complete deterministic/offline release gate: **PASS**
- Paid OpenAI/live network tests are not required by the gate.

## Persistence boundary

This consolidation intentionally does not include `.env`, `data/`, API keys, canonical memories, relationship state, developed-self state, local caches, generated frontend output, or personal VRM/Vroid source assets.
