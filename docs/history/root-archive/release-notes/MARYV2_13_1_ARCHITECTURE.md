# MaryV2 13.1 Architecture — Realtime Cognitive Infrastructure

## Design rule

**Character state is authoritative; models, retrieval indexes, perception providers and compute nodes are replaceable resources.**

```text
Clients: Desktop / Mac / iPhone / Web
                  │
                  ▼
       Realtime Interaction Coordinator
                  │
          ┌───────┴────────┐
          │                │
      Attention Bus    anti-echo / interruption
          │
          ▼
       Canonical MaryApplication
          │
  ┌───────┼─────────┬──────────┬──────────┐
  │       │         │          │          │
Identity Memory Relationship  Agency    Growth
  │       │         │          │          │
  └───────┴─────────┴──────────┴──────────┘
                  │
             Cognition
                  │
        ┌─────────┴──────────┐
        │                    │
 Hybrid Retrieval       Model Router
 lexical + vector       local + cloud
        │                    │
        └─────────┬──────────┘
                  │
           response / voice

Replaceable capability plane
  ├─ current local runtime node
  ├─ future home GPU node
  ├─ future cloud core services
  ├─ future perception providers
  └─ future specialist tools
```

## Attention is not authority

`AttentionBus` answers one question: **what deserves processing first?** It does not answer whether an event is true, durable, creator-authored or self-defining.

Every event retains a source. Only a tiny meaningful window may enter cognition, labeled `context_only`.

## Realtime lifecycle

`RealtimeInteractionCoordinator` supplies one shared state vocabulary to clients and speech systems. It can detect when new creator input arrives while Mary is represented as speaking and increment an interruption generation. Server STT rejects microphone audio while Mary is speaking when anti-echo is enabled.

The coordinator stores no chain of thought and owns no durable character state.

## Perception boundary

`PerceptionDirector` accepts bounded objective descriptions from future perception providers and forwards them to AttentionBus. Raw frame/audio payload keys are stripped from stored/status metadata.

The system prompt explicitly distinguishes `context_only` / `environment_context_only` observations from authoritative TurnMindState.

## Hybrid retrieval

`HybridReservoirRetriever` combines existing lexical/FTS results with optional semantic similarity.

`SemanticVectorIndex` is SQLite-backed and dependency-light. Vectors are stored with a content hash. Before returning a vector candidate, the retriever loads the current canonical reservoir record and rejects the vector if its content hash is stale.

This means:

```text
vector similarity → candidate
canonical reservoir record → content/provenance/confidence
Mary memory/relationship systems → truth authority
```

In `auto` mode, semantic search stays dormant until an index already exists, preserving ordinary latency and avoiding hidden Ollama calls.

## Compute node model

`NodeRegistry` describes capability, locality, privacy, cost class, connectivity and heartbeat. 13.1 automatically registers the current runtime. Node selection can prefer private/local/free capability providers.

No node descriptor contains Mary identity or persistent state. The model is intentionally transport-agnostic so a later cloud-control-plane/home-agent implementation does not require rewriting the character core.

## Explicit feedback dataset

`ResponseFeedbackStore` is a separate opt-in private evaluation store. A conversation alone is not training consent. Only explicit creator feedback records a turn. This dataset can later support regression evaluation, preference testing or supervised adapter/LoRA preparation.

It is explicitly excluded from Mary memory, GrowthEngine evidence and self-provenance.

## Reference-derived engineering patterns

13.1 adopts architectural lessons—not copied implementations—from realtime character projects:

- unified priority/event flow for simultaneous input sources;
- anti-echo and interruption as first-class state;
- perception describes before personality interprets;
- replaceable AI/speech/perception capabilities;
- local/remote capability nodes separated from character identity;
- control/state traffic conceptually separate from future high-rate audio/video data paths.

Mary's distinguishing constraint is preserved: these mechanisms surround the canonical persistent character instead of replacing it with an LLM prompt.
