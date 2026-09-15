# MaryV2 13.8 — Relational Presence & Shared Life

## Goal

13.8 closes the gap between **Mary knows her creator** and **Mary shares an ongoing life with her creator** without creating a second Mary, second relationship database, or autonomous messaging agent.

Mary remains the same canonical identity. Romantic/partner behavior is a relationship mode over that identity, not a persona fork.

## Public patterns studied

The implementation direction was cross-checked against public companion/VTuber/agent work including:

- Project AIRI: event/plugin-oriented realtime character architecture, multiple embodiment surfaces, game/voice integration.
- Open-LLM-VTuber: local/offline companion, desktop-pet mode, visual perception, interruption, Live2D expression mapping and modular Agent/STT/TTS adapters.
- Pipecat: realtime conversational turn-taking, VAD/semantic turn completion, interruption and transport separation.
- Letta/MemGPT-family memory architecture: distinction between always-relevant identity/context and larger archival memory.
- Mem0/GraphRAG patterns: relationship/entity projections that improve retrieval without making the graph the sole truth source.
- Local companion community work: local-first voice stacks, diary/reflection experiments, avatar presence and hybrid local/cloud resource tiers.

These projects reinforce useful patterns, but Mary does not adopt their identity model wholesale.

## Canonical decisions

### Relationship mode

Supported modes are `friend`, `close`, `romantic`, and `partner`.

Mode changes are recorded through the existing `RelationshipHistory` as `relationship_mode_changed` events and persisted by the existing `RelationshipManager`. There is no `girlfriend.json` and no second relationship database.

### Shared activities

Mary may hold one active shared activity in process-local state. Examples include movie/video, game, writing, drawing, study, stream, music, date, and work sessions.

Only completion becomes durable, using the existing canonical `shared_experience` relationship-history event. Notes are bounded and activity cancellation is non-durable.

### Proactive presence

`RelationalPresenceRuntime` may create bounded **proposals** such as an unfinished conversation, creator return, approaching shared event, or relevant remembered topic. It cannot send a message by itself. Existing autonomy/permission/surface scheduling remains authoritative.

### Social graph

13.8 introduces a derived social graph projection over existing relationship/profile/history information. It is not a Neo4j dependency, not a new memory store, and not truth authority. The first projection contains Mary, creator, relationship mode, explicit interests/goals/preferences, and recent shared experiences.

A future retrieval experiment may score this projection alongside semantic/keyword retrieval, but promotion into canonical memory remains governed by existing owners.

### Social delivery envelope

`SocialDeliveryPlanner` projects existing relational + emotional state into provider-neutral performance hints: warmth, playfulness, intimacy, energy, pace, pause density, teasing, and softness.

TTS/avatar providers may interpret supported hints. They do not determine Mary's relationship state or emotional truth. Public/performance scope deliberately suppresses intimacy compared with private scope.

## Companion guardrails

A convincing romantic companion does not require manipulative retention behavior. 13.8 explicitly rejects exclusivity demands, guilt for time spent offline, fake physical suffering when the creator leaves, relationship streak pressure, and cloning Mary into a separate romantic persona.

Affection, teasing, shared rituals, contextual callbacks and romantic delivery are allowed as relationship expression.

## Next implementation slices

1. Wire explicit Core/runtime actions for relationship mode and shared activities.
2. Expose safe read-only relational-presence status to Desktop/PWA/native iPhone.
3. Add shared-activity UI: Watch, Game, Create, Study, Date and Work.
4. Feed the social delivery envelope into ElevenLabs/local TTS adapters where supported.
5. Add avatar semantic actions (`look_at`, `wave`, `sit`, `react`, `idle_variant`) through existing bounded capability contracts.
6. Benchmark semantic turn detection/barge-in against the current voice path before replacing working components.
7. Evaluate social-graph-assisted retrieval on a held-out continuity set before enabling it in production prompts.
8. Add contextual-selfie generation only through canonical Mary appearance references and explicitly authorized creative services.

## Non-goals

13.8 does not move identity into an LLM, add arbitrary shell execution, make any external service a startup dependency, make romance mandatory for other Mary deployments, let generated images become identity authority, or let proactive presence bypass Mary autonomy/permission rules.
