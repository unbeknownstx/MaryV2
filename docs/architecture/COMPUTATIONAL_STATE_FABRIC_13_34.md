# MaryV2 13.34 — Computational State Fabric

**Status: DESIGN TARGET / NOT YET A PRODUCTION IMPLEMENTATION**

13.34 formalizes a distinction already implicit throughout MaryV2: Mary's identity and continuity must not depend on any one model process, inference cache, compute node, index or frontend.

> Source plus canonical durable state must be sufficient to reconstruct Mary. Losing rebuildable, warm or ephemeral state may cost time or capability, but must not erase Mary's identity, relationship continuity or accepted memory.

## Four state classes

### A. Canonical durable state
Authoritative state that must survive restart and participate in backup/recovery:
- approved authored character evidence and source fingerprints;
- relationship model/history/milestones and creator directives;
- durable episodic and semantic memory;
- developed-self and governed preference state;
- goals, intentions, curiosities and growth journal;
- durable trusted-device identity;
- durable shared/project state owned by canonical Mary systems.

### B. Rebuildable derived state
Useful projections that can be regenerated:
- FTS/vector indexes and embeddings;
- temporal/provenance projections;
- derived social/entity graphs;
- document evidence indexes;
- retrieval caches;
- hardware benchmark summaries;
- non-authoritative observability rollups.

### C. Warm computational state
Acceleration artifacts that make Mary faster without defining who she is:
- resident model weights;
- KV cache;
- prefix/prompt cache;
- compiled kernels/graphs;
- runtime-specific attention/cache pages;
- reusable embedding/inference caches;
- warmed STT/TTS/vision models.

Warm state may live in VRAM, RAM, NVMe or a future remote cache service. Reusable artifacts must be fingerprinted by model/checkpoint, tokenizer, runtime/cache format, prefix/token hash, privacy/conversation namespace, and precision/quantization where relevant.

**KV or prefix cache is never Mary memory.**

### D. Ephemeral runtime state
Expected-to-disappear execution state:
- in-flight generations;
- raw hidden states/latent tensors;
- realtime attention claims;
- partial speech/audio buffers;
- temporary node sessions and work claims;
- provider cooldowns;
- transient tool execution context;
- partial verifier/candidate scratch data.

## Recovery levels
1. **R0 — continuity recovery:** source and canonical durable state reconstruct one valid Mary.
2. **R1 — cognitive recovery:** indexes/projections are rebuilt or restored.
3. **R2 — capability recovery:** approved nodes/providers/tools reconnect.
4. **R3 — warm recovery:** important models/caches become resident again.

A system may be R0-valid while still cold and slow.

## Current implementation reality
Today, canonical `MemoryManager.save()` serializes episodic and semantic memory. Working memory remains bounded process/session state unless information is explicitly promoted into a durable owner.

13.24 already follows detect -> measure -> promote for inference acceleration. 13.34 extends the same principle to cache/storage tiers.

## Future home-server role

```text
home server
  ├─ canonical-state replica/backup under explicit authority
  ├─ rebuildable retrieval/document indexes
  ├─ RAM/NVMe warm cache tiers
  ├─ observability/benchmark store
  └─ node/capability coordination
        ├─ Windows GPU worker
        ├─ Apple Silicon worker
        ├─ mobile/edge workers
        └─ optional cloud providers
```

A large GPU is optional; the server can be useful first as always-on storage, coordination, indexing and cache infrastructure.

## KV/prefix-cache observability target
Before promoting a persistent/shared cache backend, diagnostics should compare:
- input/context tokens;
- cached/reused tokens;
- cache hit/miss rate;
- estimated KV bytes by tier;
- VRAM/RAM/NVMe residency;
- TTFT;
- decode tokens/second;
- promotion/demotion/eviction counts;
- warm versus cold latency;
- model/runtime/cache fingerprint;
- privacy namespace.

Content must not be logged merely to measure cache performance.

## Planned implementation sequence
1. Add a typed computational-state classification registry.
2. Inventory current canonical/rebuildable/ephemeral owners.
3. Add content-free cache/residency metrics to local inference/node diagnostics.
4. Benchmark current Ollama/llama.cpp/MLX behavior on real Windows/M1 hardware.
5. Add optional prefix/KV cache adapters only where runtimes expose safe semantics.
6. Evaluate RAM/NVMe/shared-cache systems on future server/GPU hardware.
7. Promote only measured winners; cache failure must always degrade to cold inference.

No persistent cache service is a Core startup requirement.
