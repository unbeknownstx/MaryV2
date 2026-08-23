# MaryV2 12.12.2 — Natural Conversation Calibration

12.12.2 keeps the 12.12 Cognitive Reservoir / Character Runtime and calibrates
how that fast local mind is presented in real conversation.

## What this pass is for

- ordinary Mary should sound like she is simply talking, not performing herself
- social and normal dialogue should usually stay short unless detail is useful
- emotion should nudge a conversational baseline rather than turn every line into a dramatic profile
- local/mind and local/system responses must remain model-free and extremely cheap
- voice payload transport should not add a fixed second of avoidable desktop latency
- local model candidates are benchmarked on the real host before any model is promoted
- voice candidates can be A/B tested without changing Mary's identity architecture

## Canonical Windows project

```text
C:\Users\Melvin\Documents\GitHub\MaryV2
```

After pasting this release over the canonical project, run:

```powershell
powershell -ExecutionPolicy Bypass -File .\SETUP_WINDOWS.ps1
```

Then launch:

```powershell
.\.venv\Scripts\Activate.ps1
powershell -ExecutionPolicy Bypass -File .\scripts\launch_windows.ps1
```

## Fast live calibration

Watch the terminal trace. 12.12.2 adds UI/audio startup stages around the existing
pipeline and TTS measurements so the remaining playback delay can be separated
into payload delivery, media readiness, play request and actual speaking start.

Useful live prompts:

```text
hey mary
how are you?
what have we been working on?
what do you think about the way you sound right now?
```

The first three should stay local whenever Mary's represented state can answer
them. Open-ended turns may escalate to a language model.

## Local model lab

Do not replace the current Qwen model first. Pull a small comparison set:

```powershell
powershell -ExecutionPolicy Bypass -File .\scripts\pull_local_model_candidates.ps1
```

For a wider test set:

```powershell
powershell -ExecutionPolicy Bypass -File .\scripts\pull_local_model_candidates.ps1 -Extended -Reasoning
```

Then benchmark the installed candidates:

```powershell
powershell -ExecutionPolicy Bypass -File .\scripts\benchmark_local_models_windows.ps1
```

The report scores latency, character fit and conversational restraint, but does
not auto-promote a model. Sample review remains a human decision. If a model wins,
select it explicitly with:

```powershell
powershell -ExecutionPolicy Bypass -File .\scripts\select_local_dialogue_model_windows.ps1 -Model qwen3:1.7b
```

This changes only the non-secret conversation-model setting and leaves the main
Ollama model available as a richer/private reference engine.

## Voice lab

The Voice Lab is offline/no-cost by default:

```powershell
powershell -ExecutionPolicy Bypass -File .\scripts\run_voice_lab_windows.ps1
```

List account voices only when you explicitly want an ElevenLabs API request:

```powershell
powershell -ExecutionPolicy Bypass -File .\scripts\run_voice_lab_windows.ps1 -ListVoices
```

Generate a comparison pack only when explicitly requested:

```powershell
powershell -ExecutionPolicy Bypass -File .\scripts\run_voice_lab_windows.ps1 -Synthesize
```

The default comparison profile deliberately uses restrained, ordinary delivery.
Mary's current voice should be judged under that direction before replacing it.

## VS Code + Codex workflow

Open the canonical `MaryV2` folder in VS Code. Codex should read `AGENTS.md`,
`CURRENT_STATE.md`, `DEVELOPMENT_PLAN.md`, and `CODEX_WORKFLOW.md` before editing.
Never expose `.env` values and never use real persistent `data/` as test state.

VS Code tasks are included under `.vscode/tasks.json` for Fast Check, Full Tests,
Release Gate, Desktop Launch and Local Model Lab. GitHub Desktop remains the safe
commit/push workflow.

## Release boundaries

The Cognitive Reservoir remains derived/rebuildable state. Existing memory,
relationship, values, preferences, developed self, knowledge and agency systems
remain authoritative. The audio cache and benchmark reports are presentation /
development artifacts and are not durable Mary memory.
