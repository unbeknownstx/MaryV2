# MaryV2 13.11 — Home Compute Fabric

## Goal

Use the creator's existing Mac, Windows PC, local models and cloud providers as one bounded heterogeneous capability pool beneath one canonical Mary Core. 13.11 is not a second agent framework and does not move identity, memory, relationship, permissions or autonomy to a device node.

## Principles

- **One Mary, many workers.** Nodes compute; Core owns Mary.
- **Benchmark first.** Metal/Vulkan/local-model usefulness is measured on the actual machine instead of assumed from model names or GPU marketing.
- **Fast and slow lanes stay separate.** Realtime conversation can remain on a fast provider while slower generation, indexing, perception or analysis work happens elsewhere.
- **Capability is not permission.** Benchmarking/routing cannot authorize device work. Device tasks still require the existing local allowlist and bounded executor.
- **Operational evidence is disposable.** Benchmark profiles contain synthetic timings only, never prompts from Mary, conversation text, memory, credentials, identity or relationship state.
- **Graceful degradation.** Either home node may disappear without making Core unhealthy.

## Components

### `mary.distributed.resource_profile`

Detects portable resource hints including CPU threads, memory, Apple Silicon/Metal visibility, Vulkan-loader visibility, optional creator-supplied GPU label/VRAM, and local runtime availability for Ollama, llama.cpp and whisper.cpp.

The RX 480 and other non-CUDA GPUs are treated as **benchmark candidates**, not hard-coded successes. If Vulkan is present, policy recommends measuring llama/whisper/preprocessing behavior before assigning work.

### `mary.distributed.benchmarking`

Creates a sanitized 13.11 benchmark profile using:

- deterministic local CPU reference work;
- optional fixed synthetic Ollama/llama.cpp generation probes;
- no Mary memory, chat, files or private prompt content.

Profiles live outside the source tree and can be rebuilt at any time.

### `mary.distributed.nodes.NodeRegistry`

Equivalent connected nodes remain ordered by existing readiness/privacy/local/cost policy, then by benchmark reliability/latency when sanitized measurements are present. Unbenchmarked nodes remain fully compatible.

### `mary.distributed.compute_fabric`

Provides richer workload-aware ranking for future/current orchestration where realtime/background intent is known. It can account for measured latency, success rate and ephemeral load, including protecting a stream-critical machine from background work. It is a scheduling hint only and cannot execute anything.

### `scripts.run_home_node`

Cross-platform node host for macOS, Windows and Linux. It reuses:

- durable Mary Protocol enrollment;
- existing local permission file;
- existing `DesktopCapabilityNodeAgent`;
- bounded Ollama/llama.cpp executors;
- bounded MCP fabric executors;
- benchmark metadata when supplied.

There is no shell task or arbitrary command executor.

### `scripts.benchmark_home_node`

Produces the benchmark profile used by the home node.

## Current-home target assignment

The assignment below is a starting hypothesis only; tonight's measurements decide the actual winners.

| Work | Preferred starting host | Why |
|---|---|---|
| Canonical identity/memory/routing | Cloud Core | Single authority; lightweight and always reachable |
| Fast social conversation | Groq / configured fast route | Lowest likely perceived latency |
| Local private conversation/utility | Best benchmarked local node | Falls back without cloud and keeps private lanes local |
| STT / VAD | Mac M1 candidate | Metal-friendly local audio workload; benchmark before locking |
| OBS / stream relay / screen capture | Windows | Stream source is physically on this machine |
| Screen/perception preprocessing | Windows CPU/RX 480 Vulkan candidate | Keeps raw screen data local; measure Vulkan vs CPU |
| Embeddings/indexing/summaries | Idle local node | Background work should use otherwise-idle compute |
| Heavy reasoning/vision/generation | Cloud specialist or queued local worker | Does not block realtime conversation |
| Avatar renderer | Windows initially | Co-located with OBS; renderer remains presentation-only |

## Tonight's bring-up

Run on **both** machines after pulling main:

```bash
python -m scripts.benchmark_home_node --local-llm --repeats 3
python -m scripts.run_home_node
```

If the profile is written somewhere custom:

```bash
python -m scripts.run_home_node --benchmark-profile /path/to/node_benchmark_13_11.json
```

Windows PowerShell can optionally label currently known GPU hardware before benchmarking/registration:

```powershell
$env:MARY_NODE_GPU_LABEL="AMD Radeon RX 480"
$env:MARY_NODE_GPU_MEMORY_GIB="4"
```

These labels are descriptive only; they never cause routing by themselves.

## Follow-on empirical tests

1. Compare Ollama/llama.cpp latency and token throughput on Mac vs Windows CPU/Vulkan paths.
2. Compare whisper.cpp on M1 Metal vs Windows CPU/Vulkan.
3. Mark Windows stream-critical during OBS testing and verify background jobs migrate away from it.
4. Measure Core -> selected node -> Core round-trip latency over the real home network.
5. Keep fast conversation independent from queued generation/perception so a slow local job never freezes Mary.
6. Attach Live2D/2.5D/3D presentation only after speech/attention/stream timing is stable.

## Deliberate non-goals

- no distributed identity or memory authority;
- no automatic training from conversations;
- no arbitrary shell execution;
- no assumption that RX 480 acceleration is useful until measured;
- no mandatory local model, MCP server, STT engine or creative service at Core startup;
- no requirement to wait for future GPU hardware.
