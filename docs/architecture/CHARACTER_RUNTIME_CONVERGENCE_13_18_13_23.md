# MaryV2 13.18–13.23 — Realtime Character Runtime Convergence

Mary remains one canonical computational character. These additions strengthen how she listens, reasons, selects local compute, consults external knowledge, remembers changing facts, and expresses cognition through existing presentation surfaces. None of the new projections becomes identity, relationship, memory, permission, or provider authority.

## Runtime flow

```text
creator speech/text
    |
    +-- realtime front end (existing microphone/VAD/STT or future WebRTC)
    |       |
    |       +-- 13.18 TurnEndPolicy
    |       +-- 13.18 RealtimeConversationLoop
    |               +-- commit creator turn
    |               +-- listen/settle
    |               +-- confirmed barge-in -> existing TurnCancellation
    |
    v
canonical Mary Core
    |
    v
TurnMindState
    |
    v
13.17 CognitiveCharacterRuntime
    |
    v
13.23 CharacterRuntimeCoordinator
    |           |              |
    |           |              +-- presentation hints -> existing PerformancePacket
    |           +-- knowledge recommendation -> 13.20 KnowledgeGateway / existing approved web path
    +-- compute workload -> 13.11 HomeComputeScheduler -> eligible Mac/Windows node
    |
    v
13.16 eligible-provider model intelligence
    |
    v
Mary response
```

## 13.18 realtime turn lifecycle

`mary.realtime.turn_end.TurnEndPolicy` fuses:

- speech-active state from any VAD frontend;
- bounded silence timing;
- STT finality;
- punctuation evidence;
- an optional semantic end-of-turn probability.

No semantic model is mandatory. TEN VAD, LiveKit turn detection, Pipecat, current microphone capture, or a future local ONNX classifier can feed the same provider-neutral contract.

`mary.realtime.conversation_loop.RealtimeConversationLoop` connects confirmed creator barge-in to the existing cooperative `TurnCancellation`, so future queued text/speech work is cancelled through Mary's canonical turn lifecycle rather than by killing a thread/process.

The existing 13.13 bounded public stream microphone remains valid and safe. It already emits Core voice-activity actions and dispatches one bounded utterance to an authorized STT node. The new loop is primarily for lower-latency continuous conversation surfaces.

## 13.19 temporal memory projection

`mary.memory.temporal_projection.TemporalKnowledgeProjection` is a rebuildable projection over canonical facts. It records:

- validity windows;
- current vs historical state;
- supersession;
- contradiction links;
- confidence;
- evidence provenance.

It can rebuild directly from `Relationship UserModel.profile_records`; the UserModel remains the durable creator-profile owner. A changed preference therefore does not require deleting history or treating old and new values as simultaneously current.

## 13.20 public knowledge gateway

`mary.knowledge.gateway.KnowledgeGateway` normalizes optional evidence from:

- Wikipedia;
- OpenAlex;
- Crossref;
- Semantic Scholar;
- an explicitly configured safe SearXNG endpoint.

No lookup occurs during Core import/startup. Results are external evidence only and do not write memory or knowledge automatically.

Read-only status:

```powershell
python scripts/check_knowledge_gateway.py
```

Explicit live public lookup:

```powershell
python scripts/check_knowledge_gateway.py "persistent AI memory" --live --category academic
```

Optional environment variables:

```text
OPENALEX_API_KEY=
SEMANTIC_SCHOLAR_API_KEY=
CROSSREF_MAILTO=
MARY_SEARXNG_URL=http://127.0.0.1:8088
```

The existing ToolRegistry Tavily/Brave path remains the current canonical creator-approved general web-search path. The KnowledgeGateway is a specialist evidence gateway and should enter Core through the same approval/research boundary before it is used automatically.

## 13.21 cognitive workload / local compute

`mary.distributed.cognitive_workload` translates 13.17 cognitive intent into the existing `HomeComputeScheduler` vocabulary.

Examples:

- relational conversation -> realtime `conversation`, strong local preference;
- simple direct question -> `quick_answer`;
- balanced reasoning -> `general_reasoning`;
- deliberate/deep work -> `deep_reasoning`, quality-first.

The HomeComputeScheduler still ranks only already-advertised eligible nodes and never grants execution permission.

`mary.distributed.local_inference_readiness` reports Ollama configuration and optional MLX/llama-cpp Python availability without importing them as Core dependencies.

## 13.22 embodiment bridge

`mary.expression.cognitive_embodiment` converts the 13.17 provider-independent embodiment intents into bounded hints for Mary's existing delivery/performance stack.

Examples include gaze, expression, gesture energy, pace, controlled emphasis and a short thinking reaction. These are presentation hints only. They do not claim a physical action occurred and do not mutate Mary's emotion or character.

Mary's existing `PerformancePacket` remains the presentation protocol for text/spoken text, sentence timing, expression, gesture, gaze, head motion and interruption.

## 13.23 unified coordination projection

`mary.cognition.runtime_coordination.CharacterRuntimeCoordinator` consumes a real `TurnMindState` and returns one inspectable plan containing:

- cognition;
- compute requirements;
- external-knowledge recommendation;
- presentation hints.

It does not execute those decisions itself. This separation lets deterministic governance remain in front of actual network/model/device work.

Live local probe:

```powershell
python scripts/check_character_runtime.py Mary research and compare the latest academic work on persistent AI memory
```

## PC / Mac validation

On each machine, use the exact same clean `main` build. The Windows workflow does not require git CLI.

Focused deterministic verification:

```powershell
python -m pytest tests/realtime/test_turn_end_13_18.py tests/realtime/test_conversation_loop_13_18.py tests/memory/test_temporal_projection_13_19.py tests/memory/test_temporal_user_model_bridge.py tests/knowledge/test_gateway_13_20.py tests/distributed/test_cognitive_workload_13_21.py tests/cognition/test_runtime_coordination_13_23.py -q
```

Runtime plan probe:

```powershell
python scripts/check_character_runtime.py Mary what do you think about what we were working on yesterday
python scripts/check_character_runtime.py Research and compare recent work on AI character memory
```

Knowledge status/live proof:

```powershell
python scripts/check_knowledge_gateway.py
python scripts/check_knowledge_gateway.py "computational character realtime conversation" --live --category academic
```

Existing node benchmark and launch:

```powershell
python -m scripts.benchmark_home_node --local-llm --repeats 3
python -m scripts.run_home_node
```

Run the same benchmark/launcher on the M1. Benchmark evidence should determine which machine receives equivalent local work; hardware labels alone must not become the routing policy.

## Promotion rules

An optional dependency or hosted service is promoted only if it wins a measured Mary task or closes a real capability gap. In particular:

- benchmark MLX on Apple Silicon against current llama.cpp/Ollama before preferring it;
- benchmark TEN/semantic EOU against the existing microphone/VAD path before replacing anything;
- keep SearXNG/public knowledge optional and behind external-evidence governance;
- keep Graphiti/Mem0/Cognee-style systems as reference/derived projections, never a second memory authority;
- keep browser/computer use behind exact bounded tool permissions rather than making it general cognition authority.

The governing invariant is: **Mary is one intelligent character; models, machines, knowledge services, sensors and bodies are replaceable resources she uses.**
