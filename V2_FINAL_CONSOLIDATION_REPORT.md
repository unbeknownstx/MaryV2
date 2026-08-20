# MaryV2 Final Consolidation Build Report

## Purpose

This overlay consolidates the verified MaryV2 runtime and the final V2 hardening work into one overwrite-safe source bundle. It preserves Mary's existing character architecture and does not include personal runtime state or API secrets.

This is the **source candidate for the final V2 hard-test**, not permission to skip testing on the canonical Windows machine.

## Verified in the consolidation environment

- Python suite: **463 passed, 1 skipped**
- Diagnostics: **50 / 50 PASS**, warnings 0, failures 0, Healthy True
- Complete deterministic/offline release gate: **PASS**
- Desktop JavaScript syntax check: **PASS**
- Desktop installation verifier, including live-state surface: **PASS**
- Release hygiene: **PASS**
- Standalone source readiness: **PASS**
- No live OpenAI call was made during consolidation verification.

## Consolidated architecture guarantees

### Character / identity
- Existing Mary identity, biography, character canon, values, preferences, developed-self, creator/relationship ownership, and self-provenance boundaries remain authoritative.
- Providers are capability engines, not Mary's identity.
- Model/task output cannot directly become durable self-state.

### Bounded memory and context
- Working memory, episodic memory, semantic memory, recent dialogue, LLM context, relationship history, relationship observations/inferences/patterns/milestones, agency ledgers, task workspaces, learning/research histories, persistent knowledge, preference-promotion evidence, experiments, nested metadata, provider attempts, and backup chains are bounded.
- Single knowledge concepts also cap sources, evidence, relations, tags, and aliases.
- Retrieval is top-N/selected; persistent storage is not injected wholesale into prompts.
- Old/low-value data may be compacted or evicted according to subsystem retention rules.

### Persistence / recovery
- Critical persistent JSON paths use atomic replacement and finite rolling backups.
- Memory and relationship recovery paths are tested against corrupt primary state.
- Stale atomic-write temp files are cleaned.

### Resource / cost governance
- Provider attempts are capped.
- Token/resource counters expose compact usage metadata without storing prompts.
- Paid OpenAI remains outside `free_first`.
- Paid expert consultation requires explicit task authorization and a per-task paid-call budget.
- Offline release verification strips live OpenAI/LLM test flags.

### Orchestration
- Task Workspace remains ephemeral and non-authoritative.
- Task Orchestrator plans according to capability/privacy/cost/authority.
- Controlled Task Executor normalizes execution and preserves permission boundaries.
- Consequential/human-authority plans do not silently execute.
- Tool/research/verification operations require explicit host handlers rather than hidden autonomy.

### Live character state
- Terminal supports `/state` and `/resources`.
- Desktop bridge publishes a display-safe live snapshot.
- State includes Mary, continuity, relationship familiarity, represented mood/energy, memory count/capacities, runtime status, current task, provider/resource metadata, and privacy policy.
- Raw memories, prompts, and API keys are intentionally excluded.

### Standalone readiness
- Development resources and frozen writable state are separated.
- Frozen default data directory: `%LOCALAPPDATA%\\MaryV2\\data`.
- `MARY_PORTABLE=1` enables side-by-side portable data.
- `MARY_DATA_DIR`, `MARY_WORKSPACE_ROOT`, and `MARY_ENV_FILE` can explicitly override locations.
- Windows PyInstaller onedir source/build configuration is included.
- The executable itself must be built and hard-tested on the user's Windows machine.

## Deliberately excluded from this overlay

- `.env`
- `data/` and all personal Mary state
- API keys/secrets
- `.venv/`
- `.git/`
- `node_modules/`
- `desktop/dist/` (rebuild it on Windows after applying the overlay)
- Mary's existing VRM/Vroid model assets under `desktop/public/models/`
- caches / compiled bytecode / old generated archives

The excluded files remain in the user's existing project when the overlay is copied on top; the overlay does not delete them.

## Apply

1. Back up or commit the current known-good MaryV2 state in GitHub Desktop.
2. Extract this bundle into `C:\\Users\\Melvin\\Documents\\GitHub\\MaryV2` and replace matching source files.
3. Do not delete `.env` or `data/`.
4. Run `powershell -ExecutionPolicy Bypass -File scripts\\hard_test_v2.ps1`.
5. Rebuild desktop with `npm ci` + `npm run build` from `desktop`.
6. Run terminal and desktop acceptance tests.
7. Only after source/runtime acceptance is green, run `scripts\\build_windows.ps1` and hard-test the frozen application.
