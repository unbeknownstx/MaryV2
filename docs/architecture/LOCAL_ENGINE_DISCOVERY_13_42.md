# Bounded Local Engine Discovery 13.42

MaryV2 13.42 adds advisory discovery of local language-model runtimes without turning discovery into trust, routing authority, or a service-management subsystem.

The design mines a useful pattern from Locally Uncensored: probe known local inference endpoints in parallel and inspect their model catalog. Mary implements that pattern independently and keeps her existing one-Core / replaceable-worker architecture.

## Supported candidate endpoints

The discovery catalog includes fixed loopback candidates for Ollama, LM Studio, vLLM, LiteLLM, KoboldCpp, Jan, GPT4All, Aphrodite, SGLang, common OpenAI-compatible ports, and the optional Locally Uncensored Local API.

Several products share the same conventional port. Mary therefore does **not** claim that a response on port 8080 proves llama.cpp, LocalAI, or TGI, and does not claim that port 5000 proves text-generation-webui or TabbyAPI. Shared ports are reported as ambiguous OpenAI-compatible endpoints with aliases.

## Security and reliability boundaries

- Only fixed `http://` loopback URLs are eligible.
- LAN, public-network, and user-supplied URLs are not scanned.
- HTTP redirects are not followed.
- Each probe is time-bounded; probes run in a bounded thread pool.
- Responses are size-bounded and model lists are clipped.
- Discovery never starts, installs, downloads, configures, or stops an engine.
- Discovery never registers a provider automatically.
- Discovery never grants execution permission.

Ollama is probed through its protocol-specific `/api/tags` endpoint. Other candidates are probed through the OpenAI-compatible `/v1/models` convention.

## Relationship to Mary's provider layer

Mary already owns a generic `OpenAICompatibleProvider`. A discovered OpenAI-compatible endpoint can therefore become an **explicit provider candidate** without adding a separate transport implementation for every local application.

A candidate still must pass the normal layers:

1. creator/runtime explicitly chooses to use it;
2. 13.39 qualified model-instance identity binds evidence to the exact node/engine/model variant;
3. 13.37 benchmark/reliability evidence determines whether the instance is actually suitable for a lane;
4. existing privacy, cost, permission, and orchestration policy decides whether a request may execute.

Reachable is not synonymous with good, trusted, private enough, tool-capable, or fast.

## Locally Uncensored interoperability

If the user explicitly enables LU's OpenAI-compatible Local API, Mary can discover the conventional `127.0.0.1:8129/v1` endpoint as a candidate service. LU remains a separate process/service; it does not become Mary Core and does not gain identity or durable-state ownership.

This also preserves the AGPL boundary: Mary can interoperate through a documented local protocol without copying LU implementation code.

## Why this matters

Mary's compute philosophy is to use the hardware and engines already available. A Windows machine might expose Ollama today, LM Studio tomorrow, and a future CUDA node might use vLLM or llama.cpp. 13.42 lets the fabric discover those opportunities while leaving selection to measured evidence rather than product branding or assumptions.
