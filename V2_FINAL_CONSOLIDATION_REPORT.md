# MaryV2 V2 Breakthrough 10 — Full-System Consolidation

## Purpose

This checkpoint rebuilds the integration boundaries around the already-working
MaryV2 core from both directions without replacing Mary's established character,
memory, relationship, learning, agency, tool, desktop, or persistence systems.

The central breakthrough is a clean division of labor:

```text
Mary personal/relational conversation
    Ollama -> Groq -> Gemini -> OpenRouter

Detached factual/technical/task generation
    Groq -> Gemini -> OpenRouter -> Ollama

Private/offline
    Ollama only

Paid expert
    OpenAI, explicit one-task authorization only
```

Mary remains the persistent character/runtime. Providers remain replaceable
engines.

## New architecture

### Authoritative TurnPolicyEngine
- Centralizes personal-conversation vs task/general model purpose.
- Uses conservative chat normalization for matching only.
- Preserves the creator's exact input text for dialogue/evidence.
- Prevents broad `QUESTION`/`CONVERSATION` intent labels from deciding provider
  privacy/cost by themselves.
- Records the policy category in `/last` metadata.

### ConversationLearningBridge
- Detects explicit invitations such as `ask me anything` or `you are here to learn`.
- Selects one real unresolved relationship-curiosity gap.
- Uses zero LLM calls to choose the question.
- Never autonomously interrogates the creator.
- Never writes creator facts; the existing relationship-learning boundary still owns learning.

### Probe-safe model context
- Obvious development/test creator records remain durable and auditable.
- They are removed before creator-profile projection reaches generation or reflection.
- Probe-shaped retrieved memories are also removed from normal model-facing context.
- `/audit` remains the explicit debugging surface.

### Read-only MarySystemContract
- Verifies single-router ownership across reasoning/reflection/orchestration/expert paths.
- Verifies shared authoritative emotion state.
- Verifies conversation local-first vs task/general cloud-first routing.
- Documents the authority map without creating another source of truth.
- Terminal `/contract` exposes the display-safe contract.

### Local supervision of local conversation
- Ollama can provide Mary's everyday conversational performance.
- Its output still passes output quality, provenance, capability truth, continuity,
  emotion, and reflection.
- A bad local conversational answer can be revised locally with the same conversation
  purpose instead of silently escalating private dialogue to cloud.

### Terminal entry-point cleanup
- `python run_mary.py` now works as a thin compatibility shim.
- `python -m scripts.run_mary` remains canonical.
- Both enter the same `MaryApplication` runtime.

## Verification in the consolidation environment

- Previous Consolidation 09 baseline: **522 passed, 1 skipped**
- Breakthrough 10 integration regressions added: **18**
- Current Python suite: **540 passed, 1 skipped**
- Diagnostics: **53 / 53 PASS**, warnings 0, failures 0, Healthy True
- `verify_breakthrough_10`: **PASS**
- Complete deterministic/offline release gate: **PASS**
- No live LLM/OpenAI call is required for deterministic verification.

## Existing V2 guarantees retained

- Mary identity/character canon independent from provider engines
- bounded active context and all persistent collections
- atomic JSON persistence and finite recovery backups
- natural imperfect-input tolerance without rewriting creator evidence
- creator/Mary ownership and provenance boundaries
- mixed-script/corrupt model output rejection/failover
- capability-use truthfulness
- disagreement/correction repair without unsupported mind-reading
- grounded emotional/relationship state
- selective creator learning and explicit developed-self promotion
- task workspace/orchestrator/executor authority boundaries
- private/offline Ollama-only route
- paid OpenAI excluded from normal routes and task-authorized only
- desktop/avatar/voice/STT/TTS/barge-in lifecycle
- display-safe live state and resource counters
- Windows standalone source/build readiness

## Release-overlay exclusions

Never overwrite or package personal runtime state:

- `.env`
- `data/`
- API keys/secrets
- `.venv/`
- `.git/`
- `node_modules/`
- generated `desktop/dist/`
- VRM/Vroid source assets under `desktop/public/models/`
- caches/bytecode

## Canonical Windows verification

```powershell
python -m scripts.verify_breakthrough_10
python -m pytest tests/integration/test_breakthrough_10.py -q
powershell -ExecutionPolicy Bypass -File scripts\hard_test_v2.ps1
python -m scripts.run_mary
```

Developer convenience also works:

```powershell
python run_mary.py
```

During real acceptance, talk naturally. `/last` should show both the actual
provider and `turn_policy`; `/route` shows the separate conversation/task routes;
`/contract` shows the authority map.
