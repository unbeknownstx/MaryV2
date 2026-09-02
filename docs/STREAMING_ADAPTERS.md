# MaryV2 streaming adapters

These adapters are capability-node inputs to the same canonical Mary Core. They
do not create a second chatbot loop, identity, memory store, or relationship.

## Twitch EventSub

Current Twitch chat integrations should use EventSub WebSockets. Configure a
Twitch application/user token with at least `user:read:chat`; writing chat later
uses `user:write:chat`. Set:

```text
MARY_SKILL_TWITCH=1
MARY_TWITCH_CLIENT_ID=...
MARY_TWITCH_OAUTH_TOKEN=...
MARY_TWITCH_BROADCASTER_ID=...
MARY_TWITCH_USER_ID=...
MARY_CORE_URL=...
MARY_CORE_TOKEN=...
```

Install `requirements-streaming.txt`, then run:

```bash
python -m scripts.run_twitch_chat_adapter
```

The adapter normalizes each `channel.chat.message` EventSub event and sends it
through Core action `stream.chat.ingest`. Core-owned Streaming Presence handles
dedupe, attention scoring, creator-floor protection, and Presence publication.

## OBS

OBS 28+ includes obs-websocket 5.x. Configure the host/password in OBS Tools ->
WebSocket Server Settings and set:

```text
MARY_SKILL_OBS=1
MARY_OBS_HOST=127.0.0.1
MARY_OBS_PORT=4455
MARY_OBS_PASSWORD=...
MARY_CORE_URL=...
MARY_CORE_TOKEN=...
```

Then run:

```bash
python -m scripts.run_obs_presence_adapter
```

OBS events enter Core as bounded perception/environment observations. Scene
switching remains disabled unless separately authorized.

## Safety

- Chat is untrusted social context.
- OBS events are environment context.
- Neither adapter may directly execute Mary tools.
- OAuth tokens/passwords stay in environment/private config and are never added
  to Mary memory, logs, model prompts, or the repository.

## Cross-platform local model node

Mac, Linux, and Windows can expose locally reachable LLM runtimes to the same
canonical Mary Core without owning Mary state:

```bash
python -m scripts.node_permissions allow llm.llama_cpp
python -m scripts.run_capability_node --enroll-only
python -m scripts.run_capability_node
```

For llama.cpp, start `llama-server` first and set `MARY_LLAMA_CPP_ENABLED=true`.
Core may use the node only through the typed `llm.llama_cpp` task contract. The
node chooses the actual GGUF/LoRA combination and can reject execution locally.
