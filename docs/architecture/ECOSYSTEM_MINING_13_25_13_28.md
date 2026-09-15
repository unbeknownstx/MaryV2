# MaryV2 13.25–13.28 — Local AI Ecosystem Mining Convergence

This pass mines useful architecture patterns from current local-AI applications without installing competing Mary identities, memory authorities, chat frontends, or autonomous package managers.

The invariant remains:

> **Mary is one canonical computational character. Local models, desktop apps, Apple creative runtimes, retrieval indexes, browsers, and cloud services are replaceable resources.**

## 13.25 — Local Runtime Intelligence

Mary now describes local inference through `mary.distributed.local_runtime_catalog` rather than assuming Ollama is the only local server.

Named candidates:

- Ollama;
- llama.cpp;
- LM Studio;
- Jan;
- MLX.

LM Studio and Jan are not duplicate provider implementations. Their OpenAI-compatible local servers reuse `OpenAICompatibleProvider`, preserving the same privacy/cost/provider boundary already used by Mary.

Default loopback endpoints are descriptive defaults only. They do **not** mark a runtime as configured or online. Runtime readiness requires an explicit environment declaration or a detectable local package where appropriate.

### MTP correction

13.24 initially treated vLLM as the only verified native-MTP runtime. Current Jan/llama.cpp support shows that compatible GGUF checkpoints may expose MTP through metadata such as `nextn_predict_layers`.

13.25 therefore recognizes three bounded native-MTP runtime families:

- vLLM;
- llama.cpp;
- Jan's llama.cpp path.

For llama.cpp/Jan, a model-family name is not enough. Mary requires explicit checkpoint evidence such as GGUF `nextn_predict_layers > 0` or a deliberate checkpoint-capability declaration. The candidate still remains `benchmark_required` until measured locally.

Ollama is deliberately not claimed as native-MTP capable by this contract.

Useful environment variables:

```text
MARY_LOCAL_INFERENCE_RUNTIME=ollama
MARY_LOCAL_INFERENCE_MODEL=
MARY_LOCAL_ACCELERATION=auto
MARY_MTP_SPECULATIVE_TOKENS=1
MARY_GGUF_NEXTN_PREDICT_LAYERS=

MARY_LM_STUDIO_BASE_URL=
MARY_LM_STUDIO_MODEL=
MARY_LM_STUDIO_READY=

MARY_JAN_BASE_URL=
MARY_JAN_MODEL=
MARY_JAN_READY=

MARY_LLAMA_CPP_BASE_URL=
MARY_LLAMA_CPP_MODEL=
MARY_LLAMA_CPP_READY=

MARY_MLX_MODEL=
MARY_MLX_READY=
```

## 13.26 — Ephemeral Context Activation

`mary.cognition.context_activation.ContextActivationEngine` mines the useful part of lorebook/persona systems without creating another personality database.

An authored `ContextCue` contains:

- bounded trigger keys;
- prompt text;
- source/provenance;
- category;
- priority.

Activation rules:

- scan only a small recent-message window (default four messages);
- deterministic case-insensitive cue matching;
- leading/trailing wildcard support only;
- hard character and item budgets;
- no recursive activation;
- do not partially inject oversized facts/instructions;
- prompt projection only;
- persistence: none;
- explicit boundary: `ephemeral_context_not_memory`.

This is appropriate for project constraints, authored lore, scene rules, tool notes, temporary room/environment facts, or session-specific context. It does not supersede CharacterSourcebook, MemoryManager, UserModel, RelationshipManager, or temporal memory.

## 13.27 — Creative Capability Fabric

`mary.distributed.creative_runtime` adds a provider-neutral contract for creative workers.

Current descriptors include:

- Draw Things (Apple-local);
- local upscaler (Upscayl/Real-ESRGAN/WebGPU-style worker);
- ComfyUI;
- client WebGPU.

Allowed operations are explicit and bounded:

```text
text_to_image
image_to_image
inpaint
upscale
text_to_video
image_to_video
```

Creative runtimes are not considered candidates until a device/client explicitly advertises readiness or an endpoint. The descriptor grants no filesystem, shell, network, or Core authority. Execution must continue through Mary's bounded capability/device-task channel.

This makes an iPad/iPhone/Mac capable of becoming a real creative node when a client adapter exists rather than being treated only as a UI.

Useful environment variables:

```text
MARY_DRAW_THINGS_READY=
MARY_DRAW_THINGS_ENDPOINT=
MARY_LOCAL_UPSCALER_READY=
MARY_LOCAL_UPSCALER_ENDPOINT=
MARY_COMFYUI_READY=
MARY_COMFYUI_ENDPOINT=
MARY_CLIENT_WEBGPU_READY=
```

## 13.28 — Rebuildable Document Evidence

Mary already owns a rebuildable CognitiveReservoir, hybrid lexical/vector retrieval, and optional semantic vector index. A second AnythingLLM-style database would create conflicting state.

`mary.knowledge.document_evidence.DocumentEvidencePlanner` instead provides explicit document synchronization **into the existing derived retrieval layer**.

It supports:

- explicit approved file sets only;
- content hashing;
- new/changed/unchanged/removed decisions;
- hard file count and byte limits;
- deterministic text chunking;
- rebuildable `ReservoirRecord` generation;
- source path and content-hash provenance;
- `canonical_owner=creator_file`;
- stale-derived-record cleanup planning.

The source file remains authoritative. The reservoir/vector representation is disposable.

No automatic filesystem crawl, watcher, cloud embedding call, or startup indexing occurs merely by importing the module.

## Home-node integration

`python -m scripts.run_home_node` now includes in `runtime.resource_profile`:

- selected local inference runtime/model;
- explicitly configured inference runtimes;
- explicitly configured creative runtimes;
- acceleration method/state;
- acceleration checkpoint evidence;
- acceleration policy version.

This is capability evidence only. Node enrollment, task permissions, and Core authority remain unchanged.

## Read-only diagnostic

```powershell
python scripts/check_local_capability_fabric.py
python scripts/check_local_capability_fabric.py --runtime ollama --model qwen3:4b
python scripts/check_local_capability_fabric.py --runtime llama.cpp --model "<GGUF model>" --gguf-nextn 2
python scripts/check_local_capability_fabric.py --json
```

## Why several screenshot apps were *not* installed

- **Msty**: useful comparison/UI ideas, but Mary already has provider/model routing and should not require manual side-by-side chat windows.
- **GPT4All**: useful CPU/local-doc precedent, but another local runtime is redundant unless benchmark evidence shows a real advantage.
- **Pinokio**: autonomous package installation conflicts with Mary's bounded dependency/tool governance; it can remain a human convenience outside Core.
- **Fooocus**: useful simplified UX, but Mary's creative fabric should target composable capabilities/workflows rather than bind itself to one image UI.
- **AnythingLLM**: document/RAG patterns were mined into Mary's existing reservoir; it is not installed as a competing memory owner.
- **Backyard AI**: bounded lore activation ideas were mined; its persona system does not replace Mary's identity/relationship architecture.

## Promotion rule

Every new local service follows:

```text
discover/configure
    -> capability evidence
    -> permission/privacy eligibility
    -> benchmark when performance matters
    -> scheduler selection
    -> bounded execution
    -> measurement
```

A popular app, model family, or benchmark claim never grants Mary runtime preference by itself.
