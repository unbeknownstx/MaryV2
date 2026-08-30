# MaryV2 System Registry

This registry is the current architectural index for MaryV2. Historical stage/release documents live under `docs/history/` and do not override this map.

| Domain | Canonical implementation | Status | Authority / notes |
|---|---|---|---|
| Composition root | `mary.runtime.application.MaryApplication` | CANONICAL | One in-process Mary composition. |
| Remote authority | `mary.core.service.MaryCoreService` | CANONICAL | Owns one long-lived `MaryApplication` for remote clients. |
| Surface authority resolution | `mary.runtime.terminal`, `mary.desktop.authority`, mobile remote runtime | ACTIVE | `MARY_CORE_URL` means remote Core; no duplicate Mary. |
| Root invariants | `mary.runtime.root_authority` | CANONICAL | Executable one-Mary/context/capability rules. |
| Character bootstrap | `mary.character` / Character Core | CANONICAL | Compact fallback when no external authored source is active. |
| Authored character sources | `mary.character.sourcebook` | ACTIVE | Loads approved sources from `character_sources/active/` or explicit env paths. |
| Character evaluation | `mary.character.evaluation` | ACTIVE | Evaluation/training evidence only; not lived memory. |
| Relationship | `mary.relationship` | CANONICAL OWNER | Shared-history/creator relationship state. |
| Memory | `mary.memory` | CANONICAL OWNER | Episodic/semantic/working memory. |
| Developed self / personality | `mary.personality`, growth paths | CANONICAL OWNER | Grounded development, not raw provider output. |
| Agency | `mary.agency` | CANONICAL OWNER | Goals, intentions, curiosities, priorities, decisions. |
| Autonomy | `mary.autonomy` | ACTIVE | Bounded execution/initiative; capability != permission. |
| Emotion/expression | `mary.expression` | ACTIVE | Baseline + state + momentum/decay; does not own personality. |
| Turn context | `mary.cognition.mind_state`, continuity/context modules | CANONICAL TURN LAYER | Bounded current/recent/retrieved/authored context. |
| Reasoning/cognition | `mary.cognition` | ACTIVE | Provider-independent Mary reasoning orchestration. |
| Provider routing | `mary.llm.router` | ACTIVE | Free/cheap/private/expert routes; models never own identity. |
| OpenAI expert | `mary.llm.providers.openai`, orchestration consultation | ACTIVE, EXPLICIT | Paid specialist route only with authorization. |
| Ollama local/private | Ollama provider + device-node executor | ACTIVE | Optional local capability; headless Windows node supported. |
| Research/evidence | `mary.learning`, `mary.tools.web` | ACTIVE | External evidence remains provenance-bearing and temporary until accepted. |
| Retrieval/reservoir | `mary.mind` | ACTIVE SUPPORT | FTS/vector/cache layers are derived, not truth authority. |
| Tool permissions | `mary.tools`, `mary.distributed.permissions` | CANONICAL BOUNDARY | Consequential actions remain gated. |
| Compute nodes | `mary.distributed`, `mary.desktop.device_node` | ACTIVE | Nodes advertise/execute capabilities; never own Mary. |
| Windows headless node | `scripts.run_windows_node` | ACTIVE | Can expose Ollama without Desktop UI. |
| Desktop | `mary.desktop`, `desktop/` | ACTIVE | Presentation/capability surface. |
| Mobile/PWA | `mary.mobile`, `mobile_web/` | ACTIVE | Remote surface over Core. |
| Native mobile | `mobile_native/` | PARTIAL | Native client work; same Core authority rule. |
| Voice/STT/TTS | `mary.voice`, `mary.desktop.voice`, audio modules | ACTIVE | Provider/local voice capability + performance direction. |
| Avatar/embodiment | `mary.avatar`, desktop presentation | ACTIVE BASELINE | Current VRM/stage is baseline, not final expressive ceiling. |
| Perception | `mary.perception` | ACTIVE BOUNDED | Describe observation before Mary interprets; no automatic memory truth. |
| Creative Studio | `mary.creative`, `mary.desktop.projects` | ACTIVE BASELINE | Cross-media planning/workspace with creator provenance and approvals. |
| Creative services | `mary.creative.services` | ACTIVE CONTRACT | Capability/cost discovery; real vendor execution adapters remain service-specific. |
| Unbeknownst workspace | `projects/unbeknownst/` | CANONICAL PROJECT HOME | Book/manga/animation/audio/assets/production organization. |
| Recovery | `mary.runtime.recovery`, recovery scripts | ACTIVE BASELINE | Secret-free manifests/snapshots; derived state rebuildable. |
| State reconciliation | `mary.runtime.state_reconciliation` | ACTIVE READ-ONLY | Single root = inventory only; two+ roots required for comparison. |
| Repository structure | `scripts.verify_repository_structure` | CANONICAL HYGIENE GATE | Prevents payload/data/node_modules/history drift into active root. |
| Historical development | `docs/history/` + Git history | ARCHIVE | Provenance only; never current runtime authority. |

## Release blockers still intentionally open

- Finish and approve the Character Bible/corpus; move approved material into `character_sources/active/`.
- Expand Mary-specific character evaluation substantially from authored examples.
- Add real authorized adapters for selected image/video/audio generation services.
- Mature avatar/3D expression beyond the current baseline model.
- Continue live cross-device/Core/node testing under real provider/network failures.
- Establish an intentional production continuity dataset after development/test state is discarded.
