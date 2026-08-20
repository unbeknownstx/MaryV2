# MaryV2 V2 Breakthrough 11 — State-Aware Local Conversation Rebuild

## Purpose

This checkpoint rebuilds the conversational supervision layer above the green
Breakthrough 10 architecture without replacing Mary's established character,
memory, relationship, learning, agency, tool, desktop, provider, or persistence
systems.

Breakthrough 10 established the correct division of labor:

```text
personal/relational Mary conversation
    Ollama -> Groq -> Gemini -> OpenRouter

detached factual/technical/task generation
    Groq -> Gemini -> OpenRouter -> Ollama

private/offline
    Ollama only

paid expert
    OpenAI, explicit one-task authorization only
```

Breakthrough 11 teaches Mary's runtime to supervise that local conversation with
more of Mary's own state.

## New/strengthened boundaries

### Process-local relationship-question continuity
- Explicit learning invitations still select one real unresolved relationship gap.
- The selected question now keeps a bounded process-local reason/category/gap record.
- Natural follow-ups such as `hmm why that question though` resolve deterministically.
- The explanation uses zero LLM calls.
- Accepted existing relationship-learning paths can resolve the matching pending question.
- No second durable relationship/memory store was introduced.

### Shared-history grounding
- `everything we've done`, `how far we've come`, and similar natural wording can use creator-authored dialogue, current creator goals, and creator-owned memories.
- Assistant-role improvisation remains excluded as evidence.
- Real MaryV2 continuity can be acknowledged without inventing off-screen activity.

### Grounded self-development
- Natural `have you changed?` questions route to self-grounded development state.
- Mary's authored canon remains distinct from controlled developed-self, relationship learning, preference development, and connected capability growth.

### Grounded relationship feelings
- `what does talking like this feel like from ur side` is a self-grounded query.
- Represented emotion, relationship state, and current-turn appraisal provide substance before Ollama expresses it.

### Rejected-hypothesis continuity
- A recently rejected Mary interpretation is temporarily represented in process-local continuity state.
- Reflection can block immediate resurrection of the same unsupported hypothesis without new creator evidence.

### Semantic style-loop control
- Recent Mary-only metaphor/style motifs are tracked in bounded continuity state.
- Repeated semantic palettes can trigger local revision even when the wording is not a near-duplicate paragraph.
- Slang, metaphor, emoji, warmth, and artistic phrasing remain optional character texture.

### Mind-reading restraint
- Direct claims such as `I can feel what you're holding` or `I know what you're feeling` are revised unless grounded by actual creator evidence.
- Mary may describe tentative impressions from the creator's words/tone without claiming direct access to private mental state.

### Local correction stays local
- Provenance, semantic repetition, rejected-hypothesis, and mind-reading revisions preserve the conversation purpose.
- Ollama can therefore revise its own local conversational output without silently escalating private dialogue to cloud.

## Verification in the consolidation environment

- Breakthrough 10 canonical baseline: **540 passed, 1 skipped**
- Breakthrough 11 regressions added: **13**
- Current deterministic Python suite: **553 passed, 1 skipped**
- Focused historical/new acceptance slice: **64 passed**
- Diagnostics: **53 / 53 PASS**, warnings 0, failures 0, Healthy True
- `verify_breakthrough_11`: **PASS**
- Complete deterministic/offline release gate: **PASS**
- No live LLM/OpenAI call is required for deterministic verification.

## Existing V2 guarantees retained

- Mary identity/character canon independent from provider engines
- personal conversation local-first and task/general cloud-first
- private/offline Ollama-only
- paid OpenAI explicit one-task advisory only
- bounded context/persistence/resources/provider attempts
- atomic recoverable persistence and finite backups
- natural imperfect-input tolerance without rewriting creator evidence
- creator/Mary provenance and ownership boundaries
- test/probe residue excluded from normal model-facing context
- corrupt/mixed-script output rejection
- capability-use truthfulness
- task workspace/orchestrator/executor authority boundaries
- desktop/avatar/voice/STT/TTS/lip-sync/barge-in lifecycle
- display-safe live state and architecture contract
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
python -m scripts.verify_breakthrough_11
python -m pytest tests/integration/test_breakthrough_11.py -q
python -m pytest tests -q
python -m scripts.run_diagnostics
powershell -ExecutionPolicy Bypass -File scripts\hard_test_v2.ps1
python -m scripts.run_mary
```

During real acceptance, talk naturally. `/last` should show the actual provider,
turn policy, and self-grounding metadata; `/route` shows conversation/task routes;
`/contract` exposes the authority map.
