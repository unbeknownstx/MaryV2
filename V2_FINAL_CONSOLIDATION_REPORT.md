# MaryV2 V2 Acceptance Consolidation 06

## Purpose

This source candidate folds the full V2 consolidation plus acceptance Hotfixes 01–06 into one overwrite-safe build. It preserves Mary’s existing character architecture while incorporating failures found only through real conversation on the canonical Windows machine.

The central rule added in this pass is: **the creator should be able to talk naturally.** Mary must not require perfect punctuation, capitalization, spelling, or benchmark-style phrasing to reach the correct local/self/relationship/task path. Matching may normalize a conservative set of chat shorthand, but the original creator text remains the authoritative dialogue/evidence.

## Verified in the consolidation environment

- Python suite: **495 passed, 1 skipped**
- Diagnostics: **50 / 50 PASS**, warnings 0, failures 0, Healthy True
- Complete deterministic/offline release gate: **PASS**
- Hotfix 06 acceptance verifier: **PASS**
- No live LLM/OpenAI call was used for this verification.

## Acceptance upgrades

### Natural imperfect input
- Questions can route correctly without `?`.
- Conservative chat forms such as `u`, `ur`, `dont`, `im`, `thats`, `alot`, etc. are normalized for intent matching only.
- Original user text is not rewritten in dialogue/memory.
- Natural relationship learning can fall back to normalized parsing while retaining the original sentence as creator-owned evidence.

### Emotional / relational behavior
- Added represented `warmth` and `appreciation` states to the existing bounded emotion system.
- Relational recognition/trust can appraise before generation so the current response—not only the next turn—can reflect the interaction.
- `what do u feel in our interactions` routes to grounded self/relationship evidence and reports `self_grounded=True`.
- Emotional first-person character language remains allowed; unsupported claims that software proves biological/metaphysical subjective experience are revised.

### Conversation quality
- Compliments/recognition are feedback turns rather than accidental speech/slang queries.
- Challenges such as `i dont know if i agree why do u think that` steer toward explaining/defending/revising rather than reflexively erasing disagreement.
- Substantial near-duplicate recent Mary prose is detected and revised.
- Assistant-generated details cannot become creator/shared history.
- Shared-work continuity may use durable creator goals/project memories even in a fresh session, while never using Mary’s own dialogue as evidence.

### Provider-output quality
- Empty/replacement/null corruption remains invalid.
- Multiple unrequested characters from unexpected scripts in an English/Latin interaction are rejected before reaching Mary.
- Invalid output records a provider attempt as `invalid_output` and continues failover.
- Legitimate translation/multilingual requests remain allowed.

### Creator-state hygiene
- Obvious development/test probes remain durable/auditable rather than being silently deleted.
- Normal creator summaries filter those flagged probe records, preventing values such as `test animal = red panda` from being presented as meaningful knowledge about the creator.
- `/audit` is read-only and surfaces conservative flags.
- `python -m scripts.audit_creator_state --all` shows all creator profile records/provenance for manual review.
- Production `/help` no longer teaches a red-panda test fact as a memory example.

## Existing V2 guarantees retained

- Character canon / identity / creator ownership boundaries
- Bounded memory, context, metadata, task state, backups, logs/resource ledgers
- Atomic persistent writes and finite recovery chain
- Free-first routing: Groq -> Gemini -> OpenRouter -> Ollama
- Private/offline Ollama-only route
- Paid OpenAI excluded from free-first and task-authorized only
- Task Workspace -> Task Orchestrator -> controlled Task Executor
- Consequential tool/human-authority actions cannot silently execute
- Display-safe live character state for terminal/desktop
- Desktop voice/STT/TTS/avatar/barge-in lifecycle
- Windows standalone source/build readiness

## Deliberately excluded from release overlays

- `.env`
- `data/` and personal Mary state
- API keys/secrets
- `.venv/` and `.git/`
- `node_modules/` and `desktop/dist/`
- Mary’s existing VRM/Vroid assets under `desktop/public/models/`
- caches/bytecode/generated archives

## Canonical Windows acceptance

After overlay:

```powershell
python -m scripts.verify_acceptance_hotfix_06
python -m scripts.audit_creator_state --all
powershell -ExecutionPolicy Bypass -File scripts\hard_test_v2.ps1
python -m scripts.run_mary
```

Only after terminal/desktop conversational acceptance remains green should the Windows executable be rebuilt and frozen.
