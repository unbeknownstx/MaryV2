# MaryV2 Convergence Upgrade — Character, Context, Recovery, Cross-Media

This pass does not create V3 or a generic Instance Platform. It matures the existing MaryV2 runtime.

## Added

- Creator-authored `CharacterSourcebook` with direct DOCX/Markdown/TXT/JSON/JSONL loading.
- `[FC]/[DNA]/[AI]/[PUB]/[ALT]/[NEG]` provenance and bounded per-turn retrieval.
- Character sourcebook wired into canonical `TurnMindState` and compact LLM context.
- Mary-specific evaluation-set schema and deterministic anti-assistant checks.
- Executable `MaryRootAuthority` hierarchy and integration-graph checks.
- Emotional momentum so meaningful states can persist and naturally decay without mutating identity.
- Read-only local/cloud state reconciliation planner.
- Secret-free recovery manifests and explicit recovery snapshot tooling.
- Cross-media production planning for book, manga, animation/video, audio drama, and mixed media.
- Creator reference/provenance, style constraints, budget ceilings, and approval-aware jobs.
- Secret-free Creative Service Registry for capability/cost discovery before execution.
- Read-only repository-layer classifier for archive cleanup planning.

## Preserved

- One canonical `MaryApplication` / Mary composition.
- Existing memory, relationship, developed-self, agency, autonomy, tool, provider, Core, node, desktop, mobile, voice, and creative workspace owners.
- Paid OpenAI explicit authorization boundary.
- Ollama/private routing semantics.
- External rendering/publishing remains unimplemented unless a real authorized adapter exists.
- No `.env` or private `data/` migration is performed by this upgrade.
