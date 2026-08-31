# MaryV2 Data and Authority Flows

This is the current runtime topology, not a promise that every optional provider, node, voice backend, or creative vendor is available on a particular host.

## Intentional policy boundaries

- **One Core / one Mary:** `MaryCoreService` owns one long-lived `MaryApplication` in remote mode. With `MARY_CORE_URL`, a surface is a client and must not construct local Mary. Only an intentional standalone development launch without that variable may construct one `MaryApplication`.
- **Character evidence is read-only:** `CharacterSourcebook` reads creator-approved material (`character_sources/active/`, or explicitly configured sources). It supplies bounded provenance-bearing retrieval; it is not memory and neither model output nor a surface may rewrite it. Draft sources are intentionally excluded.
- **Models, tools, services, nodes, and surfaces are capabilities, not identity:** none owns or replaces Mary's identity, relationship, memory, agency, or developed self.
- **Autonomy is proposal-only:** it may form bounded initiative or typed work proposals. Tool use, durable changes, spending, external effects, and device execution remain permission/creator-approval decisions.
- **Retrieved evidence is not automatically truth:** vector/FTS results, web research, perception, and provider output are provenance-bearing candidates, not automatic memory, character canon, or lived experience.
- **Private and paid routes are intentional:** `private`/`local`/`offline` force Ollama; paid OpenAI is an explicitly authorized expert task, never ordinary sticky conversation routing.

## Conversation and turn flow

```text
Desktop | Mobile/PWA | Terminal | API client
                 │ input, surface metadata, requested mode, voice flag
                 ▼
        MaryCoreService (remote) OR one standalone MaryApplication
                 │ serializes state-changing creator turns
                 ▼
  Pipeline → TurnMind / engagement / dialogue / realtime coordination
                 │
      ┌──────────┼─────────────────────────────────────┐
      ▼          ▼                 ▼                   ▼
 Character   relationship      memory recall       agency/autonomy
 Core +      + continuity      + derived retrieval proposal/intent
 Sourcebook
      │          │                 │                   │
      └──────────┴──── smallest sufficient turn context ┘
                                │
                                ▼
                    reasoning / reflection / LLMRouter
                                │
                                ▼
                    response + display-safe provenance
                                │
                                ▼
       guarded post-turn memory, relationship, and growth processing
                                │
                                ▼
             TurnResponse / surface rendering / optional speech
```

The Core turn lock is intentional: current state-changing creator turns are serialized because Mary is a single-user evolving character. A surface passes identity/transport metadata but does not merge local conversation state into Core authority.

## Memory, continuity, and Experience Evolution

```text
turn trace + creator interaction + approved state changes
                 │
                 ├─► Working / episodic memory ─► bounded recall candidates
                 ├─► RelationshipManager ───────► shared-history continuity
                 └─► ExperienceJournal/GrowthEngine ─► represented development
                                                        │
                                                        ▼
                                             developed preferences/milestones
```

Memory storage and relationship commitment are guarded lifecycle decisions, not an unconditional transcript dump. Semantic promotion is not automatic during ordinary conversation. Growth accepts grounded post-turn experience as evidence; **model dialogue alone cannot rewrite Mary**. The Experience Projector may read a safe dashboard/turn trace and turn it into theme and UI cues for desktop or mobile. It is presentation-only: it cannot write memory, alter relationship state, select a model, grant permission, or decide emotion.

CharacterSourcebook is distinct from lived memory; character evaluation and explicit response feedback are evaluation/training evidence only; growth is distinct from raw model language; derived retrieval indexes/caches are rebuildable and not state authority.

## Autonomy and capability flow

```text
agency goals / creator request / bounded trigger
                 │
                 ▼
          AutonomyRuntime → proposal / typed intent / preview
                 │
      policy and ToolManager permission boundary
          │ denied, pending, or creator-approved
          ▼
  local tool | Core workspace action | typed capability task
```

Capability availability never means permission. `MaryCoreService.preview_capability_task` does not execute. Dispatch queues a narrowly typed task; the selected device retains local execution permission. There is no arbitrary shell-command capability contract. Core workspace mutations use the same Core lock as turns and remain bounded canonical workspace actions. Creative-service discovery reports capability/cost metadata and does not itself execute a vendor job or authorize spending.

## Distributed-node flow

```text
capability node (Windows/Mac/future compute)
   │ creator-authorized enrollment + advertised capability
   ▼
NodeRegistry in canonical Mary ─► route preview / selected node
   │                                      │
   └──── never receives identity/state ───┴─► DeviceTaskBroker typed task
                                                  │
                                  scoped node session credential
                                  + live-node check
                                  + node-local permission
                                                  │
                                           completion/result to Core
```

A headless Windows node can advertise local Ollama while Desktop is closed. Initial enrollment requires creator/Core authorization and returns one process-local node session credential; only its digest is retained by Core. Heartbeat, disconnect, task polling, and task completion require that scoped credential bound to the enrolled node ID. The creator bearer does not satisfy the node task channel, and node credentials are absent from snapshots, diagnostics, task payloads, and persisted Mary state. A live node ID cannot be replaced without its current credential. After that node is disconnected or its lease becomes stale, creator-authorized re-enrollment first expires all nonterminal work from the old session, then revokes the old digest and issues a new credential. This lets the stable device ID recover without making raw credentials durable Core state or exposing prior-session task context to its replacement.

`DeviceOllamaProvider` makes the enrolled resource available to the shared router; it does not create a second router or transfer authority from Core. Registry leases and broker task transitions share one synchronization boundary. A disconnected or stale node is removed from routing, cannot claim or complete queued work, and causes its pending tasks to expire when Core observes the unavailable lease through normal broker/status activity. No background loop is created. Loss of a node never promotes a local copy of Mary into an authority.

## Voice, realtime, perception, and performance flow

```text
microphone → STT / voice input metadata → canonical turn
response → performance direction + TTS/audio → surface playback
                         │
                  realtime coordinator
       listening / transcribing / speaking / interruption / anti-echo
```

Realtime attention coordinates ephemeral priority, interruption, and anti-echo behavior; it does not change identity or memory authority. Surface voice controls call bounded Core runtime actions in remote mode. Perception first produces objective environment context; interpretation happens in Mary's turn context, and an observation is not automatically creator truth or durable memory. Performance/public context is contextual presentation for the same Mary, not a separate identity.

## Surface and presentation flow

```text
Core state/status + response display hints
                 │ read-only, display-safe projections
                 ▼
Desktop / Mobile-PWA / Terminal / future surfaces
                 │
      UI input, requested presentation, voice/realtime events
                 ▼
              canonical Core turn/control endpoints
```

Surfaces may render avatar, expression, voice, dashboard, workspace, and Experience Projector cues. They cannot independently persist canonical relationship/memory/agency state, silently choose a different authority, or make UI styling into character canon. The avatar shares Mary's emotion state where connected; expression is not personality ownership.

## Configuration and model-routing flow

Configuration starts with dataclass defaults, then loads the host-native/private `.env` without overriding already-set environment values, then `Config.from_environment()` applies `MARY_LLM_*` values. Provider-specific model variables refine their provider (`MARY_GROQ_MODEL`, optional fast conversation model, `MARY_GEMINI_MODEL`, `MARY_OPENROUTER_MODEL`, and Ollama variables). Runtime availability filters the configured order; cloud availability is key/configuration availability, while Ollama also health-checks its endpoint.

For an individual generation, precedence is:

1. explicit per-call `provider` or `route`;
2. otherwise a process-local session override (ordinary generation only);
3. purpose policy (conversation versus task/general);
4. configured routing strategy/order and fallbacks;
5. built-in defaults.

The default **task/general free-first** order is **Groq → Gemini → OpenRouter → Ollama**. Missing/unavailable providers, failures, and rate-limit cooldowns advance to the next eligible entry. The separately configurable ordinary conversation order defaults to **Ollama → Groq → Gemini → OpenRouter** and remains free-only. `MARY_LLM_FREE_ORDER` and `MARY_LLM_CONVERSATION_ORDER` can change their respective orders, subject to the router's free-provider allowlist and final Ollama safety fallback. A private route is exactly Ollama; an expert route selects the configured expert provider (default OpenAI) only with explicit task authorization.

See also [Runtime Authority and Topology](RUNTIME_AUTHORITY.md), [System Registry](SYSTEM_REGISTRY.md), and [Reconciliation 13.2](RECONCILIATION_13_2.md).
