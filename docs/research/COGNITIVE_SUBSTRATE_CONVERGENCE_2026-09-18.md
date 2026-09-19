# MaryV2 Cognitive Substrate Convergence — 2026-09-18

This document records the design convergence behind Mary's current identity, memory, world-model, skill, planning, local-knowledge, adapter and compute-node layers.

## The missing loop

observe/retrieve evidence → resolve entities and beliefs → assemble bounded cognitive blackboard → retrieve approved procedure → advance explicit durable plan → dispatch one typed capability → verify terminal outcome → replay → durable competence/skill evidence → governed consolidation.

Nothing in that loop may silently promote provider output into identity, external text into canonical memory, fictional Mary canon into AI Mary autobiography, a learned procedure into device permission, a benchmark into model authority, or a plan into autonomous execution authorization.

## Patterns adopted

### Microsoft UFO — shared blackboard
Adopted: typed shared coordination instead of workers inheriting one another's private reasoning. Mary implementation: mary.mind.cognitive_workspace.CognitiveWorkspace. Difference: Mary's blackboard is disposable and rebuildable; canonical owners remain authoritative.
Source: https://github.com/microsoft/UFO

### Microsoft Magentic-One — task/progress ledgers
Adopted: objective/decomposition stays separate from observed progress, and stalled work remains explicit. Mary implementation: ExecutivePlanGraph, dependencies, blockers, approvals, terminal node evidence, and restart recovery of orphaned running steps.
Source: https://github.com/microsoft/autogen

### Voyager — reusable skills plus environment feedback
Adopted: repeated successful public procedures can become reusable skill candidates. Mary implementation: ExperienceReplayStore + SkillLibrary. Difference: candidates never self-approve.
Source: https://github.com/MineDojo/Voyager

### Graphiti — temporal/provenance graph
Adopted: current versus historical truth, provenance, validity and contradiction. Mary implementation: TemporalKnowledgeGraph + WorldModel. Graphiti remains optional projection/specialist rather than a canonical Mary owner.
Source: https://github.com/getzep/graphiti

### Letta — distinct memory scopes
Adopted: durable core memory, archival/search data, request context and skills remain distinct. Mary keeps MemoryManager, CharacterSourcebook, WorldModel, KnowledgeFabric, ExperienceReplay and CognitiveWorkspace separate instead of flattening them into one vector database.
Source: https://github.com/letta-ai/letta

### Project NOMAD — offline collections and rebuildable search
Adopted: huge locally owned collections, Kiwix/ZIM for cold reference, derived search indexes, local RAG and hardware-aware services. Mary implementation: KnowledgeFabric, chunked local FTS, private Kiwix, typed knowledge.search node capability and optional vector backends. Rejected: generic Docker administration authority for Mary.
Source: https://github.com/Crosstalk-Solutions/project-nomad

### Qdrant Edge
Adopted as an optional future embedded/local vector backend only. Lexical/direct retrieval remains the simple baseline and vector hits remain evidence rather than truth.
Source: https://qdrant.tech/documentation/edge/

### Project AIRI
Adopted conceptually: voice, perception, avatar/body and local inference are modular capabilities under one persistent character. Mary's existing eyes/ears, realtime attention, voice/performance and future Unity/VRM surfaces remain below Core.
Source: https://github.com/moeru-ai/airi

## Community lessons

Local-AI community discussions repeatedly point to the same problems: raw chat logs are not enough, entity resolution matters, contradiction/decay is harder than vector search, untrusted web content should not auto-persist, and embeddings should retrieve candidates rather than establish truth. Mary therefore keeps source authority, TTL world context, explicit durable evidence acceptance, exact/FTS retrieval beside vectors, and replaceable small models below Core.

## Model / LoRA convergence

Third-party adapters are benchmark inputs, never Mary. Current directly downloadable experiments now include the small rockerBOO Qwen3-4B roleplay GGUF plus a 4.6 MB Qwen3-0.6B TLDR GGUF LoRA for cheap adapter-isolation tests. A separate 397 MB Qwen3-0.6B tool-calling GGUF is cataloged as a narrow micro-cortex worker. Additional research families include ArityFlow Qwen3-4B roleplay, structured-output Qwen3-4B, execution/state Qwen3-4B experiments, Qwen2.5-VL 3B GUI-grounding adapters, and small PEFT roleplay adapters that require a different runtime/conversion path.

Rules: exact base identity is mandatory; base-only is always a control; generic-adapter-only and Mary-adapter-only are separate arms; combined stacking is evaluated only when both adapters target the exact same base/runtime; MaryBench stays held out; identity boundary, fiction boundary, epistemic honesty, relationship continuity, character restraint and tool correctness are acceptance dimensions; successful adapters remain replaceable capabilities. ModelCandidateCatalog now computes exact upstream-base plus runtime compatibility and emits base-only/single-adapter experiment arms so a PEFT adapter cannot be silently treated as a llama.cpp GGUF adapter.

## Apple Silicon Mary adapter path

mary.training.mlx_bundle prepares approved Mary Dataset v1 examples for MLX-LM without training automatically. The experiment ladder now starts with mlx-community/Qwen3-0.6B-4bit as a cheap pipeline-smoke adapter, then mlx-community/Qwen3-1.7B-4bit as the light Mary adapter candidate, then mlx-community/Qwen3-4B-Instruct-2507-4bit as the stronger quality candidate. The bundle creates train/valid/test JSONL, keeps MaryBench out, writes a conservative LoRA/QLoRA config, records exact upstream lineage and the Mary dataset fingerprint, and performs no training until the creator explicitly runs MLX-LM. mary.training.mlx_preflight additionally verifies Apple-Silicon host compatibility, local MLX packages, dataset sufficiency, config lineage and (after training) adapter lineage before the experiment is considered runnable/evaluable.
Upstream: https://github.com/ml-explore/mlx-lm

## Local knowledge tiers

Tier 0 — canonical Mary state: memory, relationship, developed self, goals. Small, backed up, authority-bearing.
Tier 1 — authored Mary/project sources: Character Bible, corpus, approved references. Creator-owned and provenance-bearing.
Tier 2 — active local working knowledge: notes, manuals, code docs, study material and project files. Chunked FTS plus optional embeddings.
Tier 3 — huge offline reference libraries: Kiwix/OpenZIM Wikipedia, Stack Exchange, books, manuals and reference sets.
Tier 4 — derived semantic index: Qdrant/Qdrant Edge or another compatible local vector backend, rebuildable from source.
Tier 5 — cold archive: raw books, media transcripts, backups and old corpora, not automatically placed in model context.

Only the smallest relevant evidence set crosses from those tiers into TurnMind.

### Knowledge regression harness

`mary.knowledge.evaluation.KnowledgeFabricEvaluator` provides a NOMAD-inspired but Mary-specific deterministic retrieval gate. JSONL cases can assert expected pack/source recall, excluded or disabled-source non-leakage, complete citation IDs, explicit pack scoping and a bounded model-facing evidence budget. It deliberately avoids an LLM-as-judge score and cannot promote retrieval into memory, truth or model authority. `scripts.evaluate_knowledge_fabric` runs the same checks against a creator-selected local registry/index.


## Closed learning-loop extensions in this pass

Mary Dataset v1 now has two read-only pre-training lenses: a corpus inventory
that measures source/label/behavior/negative/fiction/MaryBench coverage, and a
deterministic exported-dataset audit that blocks split leakage, held-out prompt
contamination and training-boundary violations. MLX bundle preparation enforces
the structural audit while keeping profile sufficiency, host preflight, training
and promotion as separate explicit gates.

Model/adapter experiments now preserve append-only content-free lineage across
review registration, benchmark evidence, explicit trial dispatch and terminal
trial outcome. Prompts and generated experimental text are deliberately excluded
from the durable experiment ledger.

Approved procedures now surface repeated failure pressure through a read-only
revision queue. The approved predecessor remains active until a creator-reviewed
revision candidate is explicitly approved. World-model contradictions are
grouped into reconciliation units so competing current claims can be reviewed
together; reconciliation still retires losing claims as history rather than
deleting evidence.

Node intelligence now projects live advertisement, readiness, device-local
authorization and demonstrated competence as separate states. Capability
self-awareness consumes this evidence together with local knowledge, procedures
and world-model state rather than relying on provider priors.

KnowledgeFabric now exposes a cheap substrate profile over registry/index
metadata: active local sources, offline reference libraries, semantic
derivatives and catalog candidates. Missing/stale derivative lineage is review
evidence only; the profile performs no corpus scan, retrieval or automatic
rebuild.

## Current ownership summary

- Identity: Mary Core / canonical identity systems.
- Creator relationship: RelationshipManager.
- Lived memory: MemoryManager.
- Authored Mary character: CharacterSourcebook.
- Current external awareness: WorldContextStore, ephemeral.
- Durable evidence/beliefs: WorldModel.
- Reusable procedures: SkillLibrary.
- Explicit work progress: ExecutivePlanGraph.
- Task outcome replay: ExperienceReplayStore.
- Demonstrated capability: CompetenceLedger.
- Huge local reference data: KnowledgeFabric plus node-local services.
- Current reasoning workspace: CognitiveWorkspace.
- Models/LoRAs: replaceable generation/specialist capabilities.
- Device actions: typed capability node plus local permission.
- Training: offline lab, explicit creator command.