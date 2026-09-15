# MaryV2 13.65 — Stable Desktop Conversation Runtime

13.65 turns the existing model/node infrastructure into a product-oriented
conversation path. The goal is deliberately narrow: opening Mary Desktop should
be enough to get a responsive, persistent Mary without VS Code, manual model
server commands, or a second identity/runtime.

## Product contract

Mary Core remains the only owner of identity, memory, relationship, developed
self, goals, lifecycle, and conversation authority. Desktop is a creator surface.
Local models are replaceable renderers/executors.

Ordinary conversation may prefer the logical provider:

```
local_device -> groq -> gemini -> openrouter -> ollama
```

Task/general routing remains cloud/free-first unless separately configured:

```
groq -> gemini -> openrouter -> ollama
```

The local_device provider is not an engine name. A device may satisfy it with
LM Studio, Ollama, llama.cpp, or a future bounded runtime. This keeps model
selection independent from Mary identity and from a particular desktop app.

## Windows qualified baseline

The current measured Windows baseline is:

- Qwen3 4B Instruct 2507, Q4_K_M
- LM Studio identifier: mary-conversation
- 4096-token runtime context
- maximum GPU offload when the host allows it
- observed on the creator RX 580 4 GB host at roughly 24 tokens/s and sub-second
  warm first-token latency

These measurements are host evidence, not a universal hardware guarantee.

## One-click startup

mary.desktop.runtime_supervisor is best-effort and bounded.

On Desktop startup it may:

1. discover the installed lms executable;
2. start the loopback LM Studio server if it is stopped;
3. verify the configured model was already downloaded;
4. load that model under the stable mary-conversation identifier;
5. mark the local runtime ready;
6. enable the Desktop capability-node bridge when product local-compute mode is
   enabled.

It never downloads model weights, writes secrets, changes Mary state, or makes
LM Studio a startup dependency. Any failure degrades to the existing free/cloud
fallback path and Mary Desktop still opens.

## Canonical remote-Core path

When Desktop is connected to Railway Core:

```
Desktop
  -> authenticated canonical Mary Core
  -> LLMRouter selects local_device for ordinary conversation
  -> DeviceLocalProvider queues llm.local
  -> authenticated Desktop/home capability node
  -> host LocalRuntimeProvider
  -> LM Studio / Ollama / llama.cpp
  -> sanitized response
  -> canonical Core turn completes
  -> Desktop voice/presentation
```

Core never sends arbitrary model paths, shell commands, or host filesystem
instructions. The device chooses the concrete runtime and model role.

## Device permission boundary

llm.local is a typed, replay-safe capability and remains device-permission
gated. MARY_DESKTOP_LOCAL_COMPUTE_AUTO_AUTHORIZE=true is an explicit host
configuration that may add only llm.local to the local permission file. It does
not grant filesystem, MCP, sensor, desktop-app, shell, or arbitrary-command
execution.

## Voice resilience

auto_fast still prefers configured ElevenLabs Flash. 13.65 adds a best-effort
local voice fallback after runtime cloud-TTS failure, so an expired key or
temporary provider outage does not have to make Mary silent when Windows SAPI
or Piper is available.

## LM Studio's role

LM Studio is useful as a model laboratory and a currently qualified runtime. It
is not part of Mary identity and it is not required forever. The stable
local_device contract lets a future bundled llama.cpp service replace LM Studio
without changing Core, memory, relationship, Desktop, or stream architecture.

## Stream direction

The same local_device conversation lane is intended for the future live stream
surface. Stream chat remains untrusted public context and enters canonical Core
through the existing stream governor/cohost path. There is still one Mary; the
stream does not get a separate chatbot or memory owner.

## Acceptance target

13.65 is successful when a configured Windows host can:

1. launch Mary from the normal Desktop/launcher path;
2. restore/reconnect canonical Core state;
3. bring up an already-installed local conversation model automatically;
4. register the bounded local model capability;
5. use local_device for an ordinary model-backed conversation turn;
6. fall back to Groq/Gemini/OpenRouter if the local runtime is unavailable;
7. synthesize voice, with a local fallback when auto_fast cloud TTS fails;
8. close and reopen without moving canonical identity/state onto the PC model.

The next product gate is sustained human conversation, not additional tool
count: long-form conversational continuity, low perceived latency, streaming
speech, interruption/barge-in, and stream-chat presence should be validated on
top of this stable startup path.
