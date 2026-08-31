# MaryV2 13.2 Reconciliation

**Scope:** documentation reconciliation of the implemented MaryV2 architecture. This is a classified inventory and evidence-based status report, not a roadmap or a claim that optional integrations are live.

## Reconciliation result

The reconciled architecture is **one canonical Mary composition with replaceable surfaces and capability nodes**. The retained authority rules are:

1. Core owns the live Mary composition and serializes state-changing turns.
2. Character Core plus a read-only, creator-authored `CharacterSourcebook` supplies character evidence; it is not lived memory.
3. Relationship, memory, developed self, agency, and emotion remain distinct subsystem owners attached to the same Mary.
4. Autonomy proposes bounded work; permissions and creator approval govern consequential execution.
5. Model routing belongs to one `LLMRouter`; models do not own character or state.
6. Nodes/surfaces provide capability and presentation only.

## Classified inventory

| Classification | System | Canonical owner/implementation | Reconciliation status |
|---|---|---|---|
| Canonical composition | Local process composition | `MaryApplication` | One in-process Mary and one `MaryEcosystem`. |
| Canonical remote authority | Core service | `MaryCoreService` | One long-lived application; serial turn lock; surfaces are clients. |
| Executable invariant | Root hierarchy | `MaryRootAuthority` | Validates one-Mary/context/capability rules; not mutable state owner. |
| Canonical character evidence | Character bootstrap and sourcebook | Character Core + `CharacterSourcebook` | Active sources/explicit paths read as bounded provenance-bearing context; read-only. |
| Evaluation only | Character evaluation and response feedback | `MaryEvaluationSet`, `ResponseFeedbackStore` | Acceptance/training evidence; not memory or identity authority. |
| Canonical durable state | Relationship | `RelationshipManager` / user model | Owns creator shared-history state. |
| Canonical durable state | Memory | `MemoryManager` | Episodic, semantic, working lifecycle; retrieval is separate. |
| Canonical represented development | Developed self/growth | personality + `GrowthEngine`/`ExperienceJournal` | Grounded experience only; dialogue alone is not durable self-evidence. |
| Canonical state | Agency | `Agency` | Goals, intentions, curiosities, priorities, decisions. |
| Active bounded coordinator | Autonomy | `AutonomyRuntime` | Proposals/initiative and bounded execution path; no authority bypass. |
| Active turn layer | Context/cognition | `TurnMind`, continuity, reasoning, reflection | Selects smallest sufficient context and shares owners. |
| Active policy owner | LLM routing | `LLMRouter` | Single shared router; normal free routes and explicit expert route. |
| Optional capability | Providers | Groq, Gemini, OpenRouter, Ollama; OpenAI expert | Availability/configuration-dependent; never identity authority. |
| Active ephemeral layer | Emotion/expression/realtime | `EmotionManager`, expression, realtime/attention | Shared emotion where connected; attention is ephemeral. |
| Active bounded evidence | Research, perception | learning/web tools, `PerceptionDirector` | Provenance-bearing candidate context; no automatic memory truth. |
| Derived support | Retrieval/reservoir | `mary.mind`, hybrid/vector index/cache | Rebuildable candidate retrieval, not truth authority. |
| Canonical permission boundary | Tools | `ToolManager`, distributed permissions | Consequential effects stay gated. |
| Active capability fabric | Nodes/tasks | `NodeRegistry`, `DeviceTaskBroker`, device-node executor | Registered nodes advertise/execute typed tasks; Core remains owner. |
| Active presentation | Desktop, mobile/PWA, terminal | surface runtimes | Remote-Core clients when `MARY_CORE_URL` is set; no duplicate Mary. |
| Partial presentation | Native mobile | `mobile_native/` | Same authority requirement; implementation remains partial. |
| Active optional presentation | Voice/avatar/performance | voice/audio, avatar, performance direction | Capability/presentation; baseline does not imply complete embodiment. |
| Canonical artifacts | Workspace/production | `MaryEcosystem`/`ProductionStudio` | Canonical project artifacts, never automatic external execution. |
| Active contract | Creative services | `CreativeServiceRegistry` | Discovery/cost contract; vendor adapters remain service-specific. |
| Active baseline | Recovery/reconciliation | recovery tools, `state_reconciliation` | Secret-free recovery and read-only inventory; derived state rebuildable. |

## Before and after

### Before reconciliation: risks the architecture explicitly rejects

```text
surface-local Mary ─┐
desktop-local state ├─ competing identity/memory/route decisions
mobile-local Mary ──┘
node/model/tool ───── assumed to be an authority because it can execute
full Bible/transcript ─ sent as an undifferentiated prompt
```

This is not the accepted topology. In particular, copying a runtime onto a device, rendering an avatar, or exposing Ollama does not create a second legitimate owner.

### After reconciliation: current authority topology

```text
                 Desktop / Mobile / Terminal / API
                              │
                       remote client protocol
                              │
                 MaryCoreService (one Core)
                              │
                one MaryApplication / one Mary
     ┌────────────┬────────────┼─────────────┬─────────────┐
     │            │            │             │             │
character     relationship   memory       agency       LLMRouter
Core/sourcebook                growth      autonomy          │
     │            │            │             │       providers/nodes
     └──── bounded, provenance-aware turn context ──────────┘
```

In intentional standalone development, the same `MaryApplication` topology runs locally only when `MARY_CORE_URL` is absent. Capability nodes register with this Core and receive only typed, permission-bounded work.

## Configuration precedence

### Authority/topology

1. `MARY_CORE_URL` present: use remote Core; do not build a local Mary.
2. `MARY_CORE_URL` absent: an explicit standalone development launch may build one local application.
3. Node registration advertises a capability; it neither changes (1)/(2) nor grants execution permission.

### Character sources

1. Explicit `MARY_CHARACTER_SOURCES` paths (semicolon-separated canonically for Windows) are used when set.
2. Otherwise discovery checks `character_sources/active/`, then `docs/character/sources/`.
3. Supported files are loaded under sourcebook limits; missing/unsupported paths are reported as load errors.
4. `character_sources/drafts/` is intentionally not automatic input.

### Providers

1. Per-call explicit provider/route wins.
2. If no per-call selection exists, a process-local session override may apply; it cannot make paid OpenAI sticky.
3. Purpose chooses conversation policy or task/general policy.
4. Environment-configured policy/order applies (`MARY_LLM_ROUTING_STRATEGY`, `MARY_LLM_FREE_ORDER`, `MARY_LLM_CONVERSATION_ORDER`, primary/fallback settings).
5. Defaults apply if unset.

Default task/general `free_first`: **Groq → Gemini → OpenRouter → Ollama**. Default conversation: **Ollama → Groq → Gemini → OpenRouter**. The private/local/offline route forces Ollama. Expert/paid/OpenAI route uses the configured expert provider only for explicitly authorized work. Availability, provider errors, and cooldowns determine the effective subset and next attempt; policy order alone is not evidence a provider was used.

## Intentionally disconnected or non-authoritative systems

These separations are design requirements, not missing wiring:

| Disconnected boundary | Why it remains disconnected |
|---|---|
| Surface-local state → canonical identity/memory | Prevents duplicate Mary and divergent continuity. |
| Capability node → identity/relationship/memory/agency ownership | Nodes are replaceable compute and may disconnect. |
| Provider output → character/sourcebook/developed-self writes | Generated text is not authorial or lived-evidence authority. |
| `CharacterSourcebook` → writable memory/character mutation | Sourcebook is read-only creator evidence. |
| Fictional/alternate/negative source labels → automatic AI lived memory | Label/provenance boundary protects the real AI-Mary continuity. |
| Retrieval/vector similarity → canonical memory truth | Retrieval proposes candidates only. |
| Perception/web research → automatic durable truth | Observation/external evidence requires provenance and acceptance. |
| Autonomy trigger → permission, spending, durable/external action | Initiative is not authorization. |
| Capability preview → task execution | Preview is explicitly non-executing. |
| Core task dispatch → node-local execution permission | Device retains permission decision. |
| Creator bearer → node task channel | Enrollment is creator-authorized, but heartbeat/poll/completion require a separate scoped token bound to the node ID. |
| Stale/disconnected node → queued task claim/completion | Shared lifecycle locking rejects delivery; pending work expires when Core observes the unavailable lease. |
| Creative-service catalog → vendor execution/spending | Capability/cost discovery is not an order. |
| Experience projection/UI theme → emotional, identity, or memory state | Presentation projector is read-only. |
| Realtime attention → identity/memory authority | Attention is ephemeral coordination only. |
| Ordinary routing/session override → paid OpenAI | Paid route requires explicit per-task expert authorization. |

## Remaining gaps and accurate status

| Item | Status | Evidence-based statement |
|---|---|---|
| Approved Character Bible/corpus depth | Open | Registry lists completion/approval and moving material to active sources as a blocker. No claim of completion is made here. |
| Mary-specific character evaluation expansion | Open | Registry lists substantial expansion as a blocker. |
| Real image/video/audio vendor execution adapters | Open | Registry says service contracts exist; selected real authorized adapters remain to be added. |
| Avatar/3D expressiveness | Baseline | Registry explicitly says current VRM/stage is baseline, not final ceiling. |
| Live cross-device/Core/node failure testing | Ongoing | Registry calls for continued testing under real provider/network failure. |
| Intentional production continuity dataset | Open | Registry says it follows discarding development/test state. |
| Native mobile | Partial | Registry classifies `mobile_native/` as partial. |
| Optional provider/node availability | Host-dependent | Runtime environment and node registry report availability; documentation cannot assert availability without a live snapshot. |
| State reconciliation | Read-only baseline | Single root yields inventory; comparison requires two or more roots. It is not a merge authority. |

## Evidence and verification

This classification is grounded in:

- `MARY_ROOT.md` (root hierarchy, source labels, persistence and one-Mary rules);
- `mary/core/service.py` (Core ownership, serial turns, typed node task flow);
- `mary/runtime/application.py` (canonical application/ecosystem composition and display-safe policy status);
- `mary/runtime/integration_graph.py` and `mary/runtime/system_contract.py` (connected-owner inventory and authority declarations);
- `mary/llm/router.py`, `mary/core/config.py`, and `mary/runtime/environment.py` (routing defaults, overrides, configuration, effective availability);
- `mary/character/sourcebook.py` (source discovery); and
- `docs/architecture/SYSTEM_REGISTRY.md` (current status and stated release blockers).

The evidence supports that the ownership and policy boundaries are implemented/documented. It does **not** prove live provider credentials, network reachability, vendor adapter completion, production data readiness, or cross-device deployment health; those require runtime-specific checks.