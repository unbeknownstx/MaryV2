# MaryV2 13.1 — Realtime Cognitive Infrastructure

13.1 is an in-place evolution of the verified 13.0 Connected Development release. It is **not a reset** and it does not create another Mary. The existing canonical `MaryApplication` still owns identity, memory, relationship, cognition, agency, growth, tools, provider routing and persistent state.

## Upgrade safely

Overlay this release on the MaryV2 project root. The archive intentionally excludes `.env`, `data/`, `.git`, virtual environments, caches, `node_modules`, provider credentials and access tokens. Your existing private Mary state stays where it already lives.

After overlaying on Windows:

```powershell
python -m scripts.check_mary_13_1
python -m pytest tests -q
python -m scripts.run_release_verification
```

Then run Mary normally. The older `python -m scripts.check_mary_13` command also remains valid and now reports the current 13.x release.

## What 13.1 adds

### Realtime Interaction Coordinator

Mary now has one deterministic interaction lifecycle for text, speech and future streaming clients:

`idle → listening → transcribing → thinking → responding → speaking`

It also represents interruption/barge-in and anti-echo suppression. This state is coordination only; it cannot become identity or memory.

### Unified Attention Bus

Microphone/text input, presence events, perception observations, tool/node events and future scheduler events can enter one bounded priority queue. Creator speech/text has high attention priority, but **priority is not authority**. A visual event can be urgent without becoming creator truth.

Meaningful pending events can be claimed into the next cognitive turn as explicitly `context_only` observations. Low-value noise stays out of the prompt.

### Objective Perception Boundary

`PerceptionDirector` establishes the rule for future screen/camera/vision providers:

1. perception provider describes what it observed;
2. raw media is not retained by this boundary;
3. Mary interprets the description through her own represented state;
4. the observation never becomes creator/identity authority merely because a vision model said it.

13.1 establishes the boundary and attention integration. It does **not** enable always-on camera/screen capture by default.

### Hybrid lexical + vector memory retrieval

Mary's local cognitive reservoir can now use real embeddings without replacing her existing memory system.

Default:

```text
MARY_VECTOR_RETRIEVAL=auto
```

`auto` preserves the fast lexical-only path until you explicitly build a vector index. No Ollama embedding request is made simply because Mary starts.

When you are ready:

```powershell
ollama pull nomic-embed-text
python -m scripts.rebuild_semantic_vectors --limit 1000
```

The derived vectors live beside the reservoir. If the vector database is deleted, Mary's canonical memories are still intact and the index can be rebuilt.

### Compute Node Registry

Mary now models computers/providers as replaceable capabilities instead of identity owners. The current runtime automatically registers itself as the first node. This is the contract we will later use for Cloud Core ↔ home PC ↔ Mac capability routing.

13.1 does **not** yet expose your home PC to the internet or create a cloud server. It prepares the safe boundary first.

### Explicit Mary evaluation/training set

The mobile chat now offers tiny optional feedback controls on Mary's latest response. A record is saved only when you explicitly rate a completed turn.

The private dataset records bounded user/assistant text plus provider/model/mode and approved tags. It is kept under `data/training/`, excluded from releases, and is **not** memory, personality or development evidence.

This gives us clean evaluation/LoRA data later instead of trying to reconstruct good Mary conversations after the new GPU arrives.

### Mobile Runtime 13.1

Protocol 4 adds status/bridge support for:

- realtime phase + anti-echo;
- Attention Bus;
- compute nodes;
- hybrid retrieval;
- semantic vector rebuild;
- speech start/end/interruption reporting;
- explicit response feedback.

The native iPhone web bundle is synchronized with `mobile_web/`.

### Desktop Runtime 13.1

Desktop Runtime & Latency now also shows Realtime Interaction, Attention Bus, Perception Boundary, Hybrid Memory Retrieval, Compute Nodes and the private Mary Evaluation Set.

## What is intentionally deferred

Games/Twitch/OBS are not part of this pass. True provider-token streaming, continuous VAD, cloud hosting, remote node transport and always-on visual perception are also later integration stages. 13.1 builds the coordination and authority boundaries they need without destabilizing the working character core.

## Recommended first PC sequence

```powershell
python -m scripts.check_mary_13_1
python -m pytest tests -q
python -m scripts.run_release_verification
python -m scripts.run_mary
```

Inside Mary, useful status commands now include:

```text
/conversation
/growth
/realtime
/nodes
/retrieval
/route
```

Do not build vectors until ordinary 13.1 behavior is verified. Lexical retrieval remains completely valid without them.
