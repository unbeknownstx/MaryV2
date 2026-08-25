# MaryV2 13.1 Release Notes

## Realtime cognitive infrastructure

- Added bounded priority `AttentionBus` with explicit source/provenance labels.
- Added `RealtimeInteractionCoordinator` with listening/transcribing/thinking/responding/speaking/interrupted lifecycle.
- Added anti-echo microphone suppression while Mary is speaking.
- Added mobile + desktop speech start/end/interruption synchronization.
- Meaningful pending attention events can enter a turn as `context_only`; prompt policy prevents them from becoming identity/creator truth.

## Retrieval

- Added SQLite `SemanticVectorIndex` with cosine similarity and content-hash freshness checks.
- Added `HybridReservoirRetriever` blending lexical/FTS and vector candidates.
- `MARY_VECTOR_RETRIEVAL=auto` keeps the existing low-latency path until an explicit vector build exists.
- Added `scripts.rebuild_semantic_vectors`; it never auto-downloads models and never changes canonical memory.

## Perception

- Added `PerceptionDirector` objective describe-before-interpret boundary.
- Raw frame/audio/base64 fields are not retained in perception status/context.
- Perception is environment context only and enters the same Attention Bus.

## Distributed-compute groundwork

- Added capability descriptors and `NodeRegistry`.
- Current runtime is automatically registered as a local compute node.
- Capability selection can prefer private/local/free resources.
- Compute nodes explicitly do not own identity or state.

## Future model training preparation

- Added private explicit `ResponseFeedbackStore` under `data/training/`.
- Mobile latest-response controls can save positive/negative Mary-fit feedback.
- No automatic conversation harvesting; only explicit feedback creates a dataset record.
- Feedback data is not memory, development evidence, or self-state authority.

## Interfaces

- Mobile protocol 4.
- Runtime UI adds Realtime, Attention, Hybrid Retrieval, Nodes and Mary Evaluation Set.
- Desktop diagnostics adds the same infrastructure views.
- New terminal commands: `/realtime`, `/nodes`, `/retrieval`.
- New doctor alias: `python -m scripts.check_mary_13_1`.

## Compatibility

- 13.0 intentional conversation, Growth Engine, Voice Lab and natural voice baseline remain installed.
- Existing 12.x milestone verification remains in the release gate.
- `.env`, `data/`, tokens, API keys, personal memories, relationship state and training feedback are never shipped in release archives.
- Games/Twitch/OBS remain deferred by design.
