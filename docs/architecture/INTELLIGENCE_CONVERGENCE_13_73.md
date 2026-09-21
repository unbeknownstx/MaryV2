# MaryV2 13.73 — Intelligence Convergence / Riko + NOMAD Mining

## Goal

Close the operational intelligence loop without creating another authority:

```text
terminal task outcome
  -> competence evidence
  -> procedure quality / revision pressure
  -> bounded procedure selection for the next explicit plan dispatch
  -> new terminal evidence
```

Identity, memory truth, world truth, permissions, node execution and model promotion remain owned by their existing systems.

## Existing Mary systems reused

The repository already contains the important owners that a naive "new agent brain" would duplicate:

- `CompetenceLedger` — durable structural outcome evidence per capability, operation, node, procedure and implementation fingerprint.
- `SkillLibrary` — creator-approved procedural memory, failure pressure and governed revision candidates.
- `ExecutivePlanGraph` — durable objectives, atomic typed steps, blockers, approvals and verification.
- `SelfIntrospection` — grounded projection of advertised/authorized/demonstrated/degrading capability state plus evidence needed.
- `ModelExperimentLedger` — exact artifact/dataset/benchmark lineage for experimental models/adapters without automatic promotion.
- `KnowledgeFabric` / `KnowledgeFabricEvaluator` — local-first evidence substrate plus deterministic retrieval regression evaluation.

13.73 therefore connects these owners instead of adding a second memory, planner, skill store or model router.

## 13.73 procedure selection

An unbound plan step may now receive an **ephemeral evidence-selected procedure** during an explicit `continuity.plan.dispatch`.

The selector is deliberately conservative:

- procedure must already be creator-approved;
- at least one verified successful terminal outcome must exist;
- procedure must not be under revision pressure;
- recommendation score must clear a bounded evidence floor;
- near-ties are refused instead of guessed;
- selection does not mutate the durable plan binding;
- node choice and local execution permission remain separate;
- dispatch remains explicit.

This makes prior outcomes capable of changing the next attempt while retaining MaryV2's authority boundaries.

## Project NOMAD mining

Public Project NOMAD material was reviewed for local/offline knowledge patterns. As of the September 2026 release line, useful patterns include:

- optional Ollama/Qdrant/RAG rather than making AI infrastructure mandatory;
- Kiwix-backed offline reference libraries;
- per-file/collection activation;
- source/date citations;
- retrieval that may decline when evidence is insufficient;
- deterministic RAG evaluation;
- explicit storage lineage and service health.

Mary already implements the majority of these patterns through `KnowledgeFabric`, per-document activation, Kiwix direct retrieval, optional Qdrant derivatives, provenance-bearing citations, retrieval modes, derivative fingerprints and `KnowledgeFabricEvaluator`. Those systems remain canonical; NOMAD is an implementation reference, not a new runtime owner.

Public references:

- https://github.com/Crosstalk-Solutions/project-nomad
- https://github.com/Crosstalk-Solutions/project-nomad/releases

## Project Riko mining

Only publicly described/publicly licensed Riko mechanisms are adopted. Patreon-only source is **not copied**.

Useful public/product patterns:

- streaming response presentation;
- GPT-SoVITS-style pluggable character voice;
- Faster-Whisper/Groq ASR choices;
- animated VRM presentation;
- desktop companion presence;
- scene/room state and movement;
- VR as a presentation surface;
- frontend state broadcast separate from the language-model loop.

Mary's equivalents remain presentation/capability systems around one Core identity. Riko's simple prompt/history architecture is not adopted as identity or memory authority because Mary already has explicit authored character evidence, relationship continuity, governed memory, world model and self-introspection.

Public references:

- https://github.com/rayenfeng/riko_project
- https://www.patreon.com/RayenAI/posts/project-riko-05-157680302

## Next slices

After the 13.73 closed-loop gate is green:

1. project capability evidence into one cross-surface "what I can actually do / what needs evidence" contract;
2. strengthen knowledge-substrate freshness and evaluation reporting rather than adding another RAG store;
3. converge Riko-style scene/avatar/voice presence onto the existing PerformancePacket and surface projection;
4. extend model/adaptor experiment evidence into the same capability self-model without granting production promotion authority.
