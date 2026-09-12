# MaryV2 engineering instructions

## Read before editing

1. `README.md`
2. `MARY_ROOT.md`
3. `docs/README.md`
4. `docs/architecture/SYSTEM_REGISTRY.md`
5. `docs/design/MARY_VISUAL_SYSTEM.md` for surface/UI work

Historical files under `docs/history/` are provenance, not current instructions.

## Non-negotiable architecture

- Many surfaces and compute nodes; **one Mary**.
- Mary is not an LLM. Providers/models are replaceable capabilities beneath Mary.
- `MaryApplication` is the canonical in-process composition root; remote surfaces use Mary Core rather than constructing another Mary.
- Identity, authored character, relationship, memory, developed self, agency, emotion, permissions, and continuity retain explicit owners.
- Provider/tool output is evidence or task output until a governed Mary subsystem accepts it; it is never durable identity by default.
- `[FC]` fictional canon is not AI Mary's lived memory.
- Capability discovery is not authorization. Paid/external/consequential actions remain gated.
- Presentation, diagnostics and operational telemetry never become identity/state authorities.

## State safety

- Repository source and mutable Mary state are separate.
- Never read, print, commit, normalize, or overwrite secret values from `.env`.
- Tests must use isolated temporary state through `conftest.py`.
- Never restore historical repo-local `data/` into canonical state merely because it is older or newer.
- Derived caches/indexes are rebuildable and must not become identity authority.

## Development workflow

- Inspect existing systems before replacing them.
- Prefer coherent source changes over patch piles or duplicate payload directories.
- Reconcile old packages into current owners; do not reintroduce a superseded subsystem just because an overlay contains it.
- Do not add `payload/`, `upgrade_backups/`, `data/`, `node_modules/`, runtime reports, or `*.pre_*` source backups to the canonical tree.
- Put historical implementation notes under `docs/history/`.
- Keep creator-authored unfinished Character Bible/corpus material in `character_sources/drafts/`; only approved material belongs in `character_sources/active/`.
- Use `python -m scripts.verify_repository_structure` after structural work.
- Use `powershell -ExecutionPolicy Bypass -File scripts\test_fast.ps1` while iterating and `python -m pytest -q` for the full deterministic gate.

## Runtime routing

- `MARY_CORE_URL` configured: Desktop/Mobile/Terminal are remote surfaces of canonical Core.
- No `MARY_CORE_URL`: explicit standalone development may construct one local `MaryApplication`.
- Windows/macOS/future machines may register capability nodes; nodes never own Mary's identity/state.
- Ollama/llama.cpp remain optional private/local capabilities and must not be required for launch.
- Paid OpenAI remains an explicit expert/specialist route, never an automatic free-first fallback.
- External MCP/creative/stream services are optional and may disappear without making Core startup unhealthy.

## Character and conversation

- Realize Mary from authored evidence and represented state; do not perform generic assistant copy with Mary catchphrases pasted on top.
- Distinctive phrases are evidence, not mandatory verbal tics.
- Growth must remain grounded and bounded by Mary's authored behavioral space.
- Emotion may persist and decay; emotional state must not rewrite baseline personality.
- Context should be selective: everything may be addressable without everything entering every prompt.
- Short social input should not trigger essay-length psychological interpretation merely because a model can generate it.

## UI / product experience

- Preserve the same information and visual roles across Desktop, SwiftUI and PWA while adapting layout natively to each form factor.
- Reuse approved Mary artwork/assets already in the repository before adding external media.
- Do not import third-party art/UI assets without explicit provenance/license.
- Renderer/voice/node/integration failures are designed degraded states; primary chat/work flows must remain usable.
- Respect reduced-motion, focus visibility, touch-target and contrast requirements.
- Ordinary screens should describe user-facing state; implementation detail belongs in Runtime/Diagnostics.
