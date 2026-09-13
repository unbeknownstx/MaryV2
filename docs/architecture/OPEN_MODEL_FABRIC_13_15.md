# MaryV2 13.15 — Frontier / Open Model Fabric

## Purpose

Mary's identity and continuity must outlive any one model vendor. 13.15 makes
that architectural rule practical: frontier language models are interchangeable
cognition capabilities behind the existing LLMRouter, not alternate Mary
instances.

The implementation adds direct, lazy OpenAI-compatible provider presets for:

- DeepSeek
- Z.AI / GLM
- Alibaba Cloud / Qwen
- Moonshot / Kimi
- MiniMax
- Cerebras Inference
- Together AI
- Fireworks AI
- one generic openai_compatible profile for future vendors or loopback local servers

Existing Groq, Gemini, OpenRouter, Ollama, llama.cpp, and explicit OpenAI expert
routes remain intact.

## Spending boundary

Adding an API key does not make a paid provider part of Mary's ordinary
free-first or relationship conversation route.

- free_first stays free/local only.
- private / local / offline still force Ollama.
- frontier / reasoning / specialist use the explicitly configured frontier order.
- expert still uses one explicitly configured expert provider.
- A direct provider request remains an intentional per-call override.

This keeps experimentation easy without turning "a credential exists" into
permission to spend.

## Token / reasoning budget

Ordinary chat keeps Mary's normal output budget. An explicit frontier,
reasoning, or specialist route receives a separate bounded output ceiling
(default 8192 tokens, configurable with MARY_FRONTIER_MAX_OUTPUT_TOKENS).
Requests above that ceiling are clamped by RuntimeLimits.

ResourceGovernor remains the accounting authority and records prompt,
completion, reasoning, cached-prompt, and total token telemetry when a provider
reports those fields. This is process-local structural telemetry only; prompt
or response text is not stored in the governor.

The intent is to spend token budget where additional reasoning can matter
without making every casual Mary turn long or expensive.

## Configuration

The default opt-in frontier order is:

~~~
deepseek -> zai -> qwen_cloud -> kimi -> minimax -> cerebras -> together -> fireworks -> openai
~~~

Override it with:

~~~
MARY_LLM_FRONTIER_ORDER=deepseek,kimi,zai,qwen_cloud,minimax,cerebras,together,fireworks,openai
~~~

Each direct provider has a model override, for example:

~~~
MARY_DEEPSEEK_MODEL=deepseek-v4-flash
MARY_ZAI_MODEL=glm-5.3-flash
MARY_QWEN_CLOUD_MODEL=qwen3.8-flash
MARY_KIMI_MODEL=kimi-k2.6
MARY_MINIMAX_MODEL=MiniMax-M2.7
MARY_CEREBRAS_MODEL=gpt-oss-120b
MARY_TOGETHER_MODEL=openai/gpt-oss-120b
MARY_FIREWORKS_MODEL=accounts/fireworks/models/deepseek-v3p1
~~~

Provider base URLs are overrideable as well. This matters for Alibaba
workspace/region endpoints, mirrors, enterprise gateways, and future API
migrations.

## Future-provider escape hatch

A new OpenAI-compatible service can be trialed without changing source:

~~~
MARY_OPENAI_COMPAT_BASE_URL=https://provider.example/v1
MARY_OPENAI_COMPAT_API_KEY=...
MARY_OPENAI_COMPAT_MODEL=vendor/model
~~~

Then explicitly request provider=openai_compatible.

For a loopback server such as a local vLLM, SGLang, or LM Studio endpoint, the
same adapter permits no-key operation and advertises zero_local plus local_only
privacy. Remote URLs never gain that local/private capability.

## Why this is distributed rather than one giant model

Mary can keep a small, fast model resident for ordinary presence while routing
harder work to a stronger local node or a frontier cloud model. The canonical
Core remains responsible for identity, memory, relationship state, governance,
context selection, and capability permission.

A model may be better at reasoning, coding, long context, multilingual work, or
vision without becoming a new personality or state owner.

## Model-license rule

Provider connectivity and model licensing are separate concerns. The registry
does not infer that every model exposed by a vendor is open source or carries
the same license. Before redistributing weights or building a commercial
self-hosted derivative, verify the license of the exact model/checkpoint.

## Next evolution

13.15 deliberately establishes the transport and policy substrate first.
Useful follow-on work is evidence-driven:

1. benchmark configured providers on Mary's real conversation, coding, tool-use,
   latency, and cost traces;
2. record token usage and cost estimates without storing prompt content;
3. promote models into purpose routes only after representative tests;
4. use home capability nodes for larger local vLLM, SGLang, llama.cpp, or other
   OpenAI-compatible services;
5. add multimodal/provider-specific adapters only where generic compatibility is
   insufficient.

The result is a model-agnostic Mary that can adopt frontier inference without
rewriting her core architecture.
