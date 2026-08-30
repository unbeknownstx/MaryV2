# MaryV2 12.12.3 - Production Hybrid Dialogue

12.12.3 promotes the validated deterministic Hybrid Dialogue architecture into
Mary's real conversation path. It does not promote Qwen or change provider
defaults.

## What changed

- `CharacterMind` now projects one immutable typed response plan before wording.
- The deterministic risk classifier separates precision-local, low-risk
  social, open conversation, and thinking-required turns.
- Eligible precision/social turns use LocalComposerV2 and an independent
  semantic, ownership, form, provenance, and capability audit.
- A complete audited result returns locally with zero provider calls. Anything
  incomplete or unsupported escalates through Mary's existing route.
- An eight-entry process-local phrase history reduces exact repetition without
  becoming memory.
- Runtime Diagnostics shows class, engine, local timings, escalation, and
  disabled shadow status without exposing semantic plan contents.

Mary's identity, memory, relationship, preferences, developed self, values,
knowledge, and capability/runtime owners remain authoritative. The reservoir
is still derived cache state.

## Canonical Windows project

```text
C:\Users\Melvin\Documents\GitHub\MaryV2
```

Run setup and verification:

```powershell
powershell -ExecutionPolicy Bypass -File .\SETUP_WINDOWS.ps1
```

Launch Mary:

```powershell
.\.venv\Scripts\Activate.ps1
powershell -ExecutionPolicy Bypass -File .\scripts\launch_windows.ps1
```

## Safe production-path benchmark

The benchmark uses fresh temporary state and an in-process counting provider;
it makes no external, paid, Ollama, TTS, or model call:

```powershell
powershell -ExecutionPolicy Bypass -File .\scripts\benchmark_production_hybrid_dialogue_windows.ps1
```

Reports are developer artifacts under `runtime_reports/`, not Mary memory.

## Expected routes

- Grounded local example: `provider=local/mind`,
  `engine=local_composer_v2`, `class=precision_local` or `social_low_risk`.
- Open conversation: the already configured fast conversation route and
  `engine=conversation_generation`.
- Technical/tool/deep work: the existing thinking/task/tool architecture.
- Private/offline: Ollama remains the optional local safety route.
- Paid OpenAI: explicit expert authorization only.

`qwen3:1.7b` remains shadow/benchmark-only and disabled in production. No local
model was selected, downloaded, called, or promoted by this release.

