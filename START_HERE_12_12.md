# MaryV2 12.12 — Cognitive Reservoir + Character Runtime

12.12 moves ordinary character operation closer to **Mary first, models second**.
It does not replace the identity/memory/relationship/cognition architecture from
previous releases.  Instead it adds a fast, rebuildable local layer over those
authoritative systems.

## Core rule

Mary is not an LLM.  The character owns her represented identity, relationship,
memory, preferences, values, emotion, continuity, agency and state.  Language
models are replaceable language/reasoning capabilities.

12.12 introduces four practical cognitive speeds:

1. **Reflex** — deterministic dialogue/character behavior; no model call.
2. **Reservoir** — local SQLite FTS retrieval over represented state; no model call.
3. **Language cortex** — fast local/cloud language model when free-form language is useful.
4. **Thinking / expert** — deeper models/tools only when the turn warrants them.

The Cognitive Reservoir is **derived cache state**.  Canonical Mary state remains
in the existing memory, relationship, personality, knowledge and development
systems.  Deleting the reservoir must never delete Mary's real state; it can be
rebuilt.

## Windows canonical workflow

Canonical project:

```text
C:\Users\Melvin\Documents\GitHub\MaryV2
```

Run setup/verification:

```powershell
powershell -ExecutionPolicy Bypass -File .\SETUP_WINDOWS.ps1
```

Launch:

```powershell
.\.venv\Scripts\Activate.ps1
powershell -ExecutionPolicy Bypass -File .\scripts\launch_windows.ps1
```

Fast development checks:

```powershell
powershell -ExecutionPolicy Bypass -File .\scripts\test_fast.ps1
```

Character-runtime checks only:

```powershell
powershell -ExecutionPolicy Bypass -File .\scripts\test_character.ps1
```

## Cognitive Reservoir

Persistent desktop/source applications place the derived database alongside the
configured Mary data tree under:

```text
<canonical data root>\reservoir\mary_reservoir.sqlite3
```

Default hard budgets:

- 50,000 derived records
- 512 MB reservoir database

Both are configurable with:

```text
MARY_RESERVOIR_MAX_RECORDS
MARY_RESERVOIR_MAX_MB
```

The first-pass reservoir indexes bounded, provenance-bearing projections of:

- structured creator facts/preferences/goals/interests/values
- Mary's represented/developed preferences
- semantic memory
- meaningful episodic/shared history
- verified knowledge concepts

FTS5 search is the default fast retrieval mechanism.  Optional embeddings are a
future-quality enhancement, not a launch dependency.

## Local model lab

12.12 does **not** force another local model onto the front line.  It includes a
benchmark harness so the real Windows PC decides what is useful.

Recommended small candidates to test on the current 32 GB RAM / 4 GB VRAM host:

```powershell
powershell -ExecutionPolicy Bypass -File .\scripts\pull_local_model_candidates.ps1
powershell -ExecutionPolicy Bypass -File .\scripts\benchmark_local_models_windows.ps1
```

The default small pull set is deliberately modest:

- `qwen3:1.7b` — character verbalizer candidate
- `gemma3:1b` — small utility/extraction candidate
- `nomic-embed-text` — optional embedding model

Existing `qwen3:4b` remains a quality/reference/private model.  Larger or
reasoning-focused candidates are opt-in.

If a local dialogue candidate wins on the actual PC, select it without replacing
the main Ollama model:

```powershell
powershell -ExecutionPolicy Bypass -File .\scripts\select_local_dialogue_model_windows.ps1 -Model qwen3:1.7b
```

This writes only the non-secret `MARY_OLLAMA_CONVERSATION_MODEL` setting after
backing up `.env`.

## Expression Director

12.12 gives voice and avatar one provider-independent `DeliveryPlan`.  It can
represent bounded performance traits such as energy, warmth, pace, stability,
emphasis, avatar expression and gesture energy.

The plan is deterministic from Mary's represented state + her already-generated
response.  It does not infer hidden creator emotion.  ElevenLabs settings and
VRM movement can therefore vary together without a second LLM call.

## Presence / autonomy

Autonomy remains game-AI-like and bounded:

- cheap idle animation and local sounds
- Focus-mode quiet behavior
- typed Presence events
- utility/initiative decisions where silence is valid
- pending thoughts only when represented state actually exists

12.12 specifically removes the unsupported idle phrase "I was thinking about
something."  Mary must not claim private ongoing thought unless a grounded
PendingThought or other represented state supports it.

## What remains optional

The following are capabilities, not launch requirements:

- OpenAI expert
- Ollama/local models
- YouTube Data API
- loopback WebSocket presence bridge
- Twitch / OBS / visual context
- local embedding model

Normal Mary must still launch when optional integrations are absent.

## Testing philosophy

- **FAST**: character/runtime critical regressions + frontend syntax
- **CHARACTER**: Cognitive Reservoir, local dialogue, expression, presence
- **FULL**: canonical Python suite
- **RELEASE**: deterministic/offline release gate and diagnostics

Tests must never use the creator's real persistent Mary state.
