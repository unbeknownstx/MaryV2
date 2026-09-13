# MaryV2 13.35 — Model Execution Fabric

## Purpose

13.35 connects Mary's existing home-compute and open/frontier-model fabrics with one missing rule:

> **Reachable does not mean executable; executable does not mean feasible; feasible does not mean preferred.**

Mary is one canonical Core with many replaceable cognition engines. A Windows PC, M1 Mac, future CUDA box, Ollama model, llama.cpp server, hosted open model, or paid specialist can all be useful without being equally appropriate for every task.

This layer is **planning and observability only**. It does not grant device execution permission, spend money, move identity/memory authority, or automatically promote an untested provider.

## Decision layers

Every candidate passes through distinct gates:

1. **Discovered** — the runtime/provider/node exists.
2. **Available** — the provider is configured or the node is live.
3. **Authorized** — existing provider-spend or device permission policy allows execution.
4. **Feasible** — measurements show the engine can complete this class of work on this hardware/service.
5. **Suitable** — latency, reliability, privacy, cost and task requirements fit the requested lane.
6. **Preferred** — representative benchmark evidence justifies promotion over alternatives.

A failure at a later layer does not erase earlier capability. A 4B model that is poor for live banter may still be excellent for private background work.

## Task lanes

| Lane | Default latency target | What matters most |
|---|---:|---|
| realtime_voice | 1.5 s | floor timing / interruption |
| social_instant | 2.5 s | banter / presence |
| conversation | 10 s | interactive quality + latency |
| private_conversation | 60 s | privacy first; slower local work acceptable |
| deep_reasoning | 180 s | reasoning quality |
| coding_agent | 180 s | correctness / tool fit |
| research_synthesis | 180 s | evidence handling / synthesis |
| long_context | 300 s | context capacity / reliability |
| background | 600 s | cost / idle compute / throughput |

These are policy targets, not hard claims about any particular model.

## Engine portfolio

### Current ordinary routes

- Groq
- Gemini
- OpenRouter
- Ollama capability nodes
- explicit OpenAI expert route

### Frontier/open provider fabric already supported

- DeepSeek
- Z.AI / GLM
- Alibaba Cloud / Qwen
- Moonshot / Kimi
- MiniMax
- Cerebras
- Together AI
- Fireworks AI
- generic OpenAI-compatible endpoints

API-key presence only makes a provider configured. It does not place a paid-capable service into Mary's ordinary free-first route.

### Local/runtime candidates

The same architecture can benchmark and later promote:

- Ollama
- llama.cpp
- MLX-backed workers
- vLLM
- SGLang
- generic loopback OpenAI-compatible servers
- future CUDA workers
- future home-server inference/cache services

Local runtime support remains hardware-dependent and must be measured on the actual node.

## Local suitability semantics

The model fabric reads sanitized node-route benchmark hints and classifies the selected local engine per lane:

- **unavailable** — no routable node;
- **experimental** — reachable but unbenchmarked;
- **avoid** — measured reliability/latency does not fit the lane;
- **feasible_slow** — slower than the target but useful for a non-realtime lane;
- **preferred** — measured evidence currently satisfies the lane.

This classification grants no execution authority.

## Current Windows interpretation

The existing Windows node proves that Ryzen/32 GB/Ollama/Qwen is a real capability. It does **not** prove that qwen3:4b-instruct should carry every Mary turn.

Until representative benchmarks are recorded:

- normal cloud conversation can remain the responsive lane;
- Windows Ollama is an explicit private/experimental lane;
- qwen3:1.7b can be evaluated for fast/utility work;
- qwen3:4b-instruct can be evaluated for private/general work;
- longer local turns are acceptable for deep/background work if quality is worthwhile;
- failure or high latency in one lane does not disqualify the engine from all lanes.

## Frontier-provider promotion

Frontier providers appear in the 13.35 catalog with configured/unconfigured status, active model, cost class, benchmark-required promotion state, and auto-promoted=false.

Mary should benchmark candidate providers on representative Mary workloads before changing default purpose routes.

Useful benchmark dimensions include:

- character/conversation quality;
- coding correctness;
- tool/function behavior;
- research synthesis;
- long-context retention;
- latency / TTFT / tokens per second;
- failure/rate-limit behavior;
- token usage and estimated cost;
- cached-token behavior where exposed.

Prompt/response content does not need to be retained in operational benchmark telemetry.

## DeepSeek current preset

The direct DeepSeek preset now defaults to `deepseek-v4-flash`, replacing the stale `deepseek-flash` alias. The model remains environment-overridable because provider model IDs evolve.

## Relationship to 13.34

13.34 classifies **state durability**: canonical durable, rebuildable derived, warm computational, and ephemeral.

13.35 classifies **execution suitability**.

Together they answer two separate questions:

1. *What must survive for Mary to remain Mary?*
2. *Which available engine should do this particular piece of work?*

A future home server can therefore hold persistence, indexes and warm caches while the model-execution fabric independently chooses the best worker for each job.

## Promotion loop

~~~text
detect
  -> expose capability
  -> benchmark
  -> compare by task lane
  -> explicitly promote
  -> keep measuring
  -> demote when evidence changes
~~~

No model, benchmark or cache becomes identity or memory authority.
