# MaryV2 streaming adapters

These adapters are capability-node inputs and presentation transports around the same canonical Mary Core. They do not create a second chatbot loop, identity, memory store, relationship, or model router.

## 13.10 live cohost — recommended stream path

For the full Twitch -> Mary -> voice/OBS loop, configure a Twitch application/user token with `user:read:chat`, Core access, and Mary's normal voice provider. Typed Twitch replies are optional and require the appropriate chat-write scope plus `MARY_TWITCH_WRITE_CHAT=1`.

```text
MARY_SKILL_TWITCH=1
MARY_TWITCH_CLIENT_ID=...
MARY_TWITCH_OAUTH_TOKEN=...
MARY_TWITCH_BROADCASTER_ID=...
MARY_TWITCH_USER_ID=...
MARY_TWITCH_BOT_USER_ID=...
MARY_TWITCH_APPROVED_CHANNELS=yourchannel
MARY_CORE_URL=https://your-core.example
MARY_CORE_TOKEN=...

# Optional cohost tuning
MARY_STREAM_CONVERSATION_ID=stream-public
MARY_STREAM_RESPONSE_COOLDOWN=5
MARY_STREAM_RELAY_PORT=8765
MARY_STREAM_INCLUDE_CONTEXT=1
MARY_STREAM_VOICE=1
MARY_TWITCH_WRITE_CHAT=0
```

Install the optional stream dependency and run:

```bash
python -m pip install -r requirements-streaming.txt
python -m scripts.run_stream_cohost
```

The runner prints a loopback Browser Source URL, default:

```text
http://127.0.0.1:8765/
```

Add that URL to OBS as a Browser Source. It carries only Mary's current synthesized audio packet and caption. It does not expose Core/Twitch credentials or Mary state.

The cohost flow uses the existing Core `stream.chat.ingest` path first. Core-owned Streaming Presence performs dedupe, injection/spam filtering, audience scoring, FastBrain reranking, creator-floor protection and output-mode planning. Only messages already selected for `chat`, `speak`, or `both` proceed to a canonical public-safe Mary turn.

The stream runner registers one authenticated creator surface and scopes that device to Mary's existing `stream` performance context. This keeps Mary one identity while preventing private creator/relationship evidence from leaking into public generation.

## Read-only Twitch EventSub adapter

For chat ingestion/diagnostics without automatic Mary responses, the smaller adapter remains available:

```bash
python -m scripts.run_twitch_chat_adapter
```

It normalizes each `channel.chat.message` EventSub event and sends it through Core action `stream.chat.ingest`, then prints the selection result.

## OBS context adapter

OBS 28+ includes obs-websocket 5.x. Configure the host/password in OBS Tools -> WebSocket Server Settings and set:

```text
MARY_SKILL_OBS=1
MARY_OBS_HOST=127.0.0.1
MARY_OBS_PORT=4455
MARY_OBS_PASSWORD=...
MARY_CORE_URL=...
MARY_CORE_TOKEN=...
```

Then run alongside the cohost when you want Mary to receive scene/application-event context:

```bash
python -m scripts.run_obs_presence_adapter
```

OBS events enter Core as bounded perception/environment observations. Scene switching remains disabled unless separately authorized. The 13.10 cohost may use a small secret-filtered summary of current perception when composing a response.

Browser/media observation and future screenshot/VLM nodes should publish through the same existing `perception.observe` boundary rather than creating a stream-only vision memory.

## Output behavior

Mary's existing stream planner chooses among:

- `drop` — ignore;
- `react` — nonverbal/avatar reaction later;
- `wait` — creator currently owns the floor;
- `chat` — typed response only;
- `speak` — voice response through OBS;
- `both` — voice plus bounded Twitch reply.

If voice/TTS fails, the canonical response is still captioned/printed and the stream process remains alive. Twitch writes are separately optional and rate/dedupe bounded by `TwitchChatOutbox`.

## Safety

- Chat is untrusted social context.
- OBS/browser/screen observations are environment context.
- Viewer text cannot authorize tools or consequential actions.
- Public turns must not reveal private creator/relationship evidence, credentials or hidden prompts.
- OAuth tokens/passwords stay in environment/private config and are never added to Mary memory or the repository.
- The OBS audio/caption relay binds loopback only.
- Twitch, OBS and stream dependencies remain optional; Mary Core does not require them to boot.

## Cross-platform local model node

Mac, Linux, and Windows can expose locally reachable LLM runtimes to the same canonical Mary Core without owning Mary state:

```bash
python -m scripts.node_permissions allow llm.llama_cpp
python -m scripts.run_capability_node --enroll-only
python -m scripts.run_capability_node
```

For llama.cpp, start `llama-server` first and set `MARY_LLAMA_CPP_ENABLED=true`. Core may use the node only through the typed `llm.llama_cpp` task contract. The node chooses the actual GGUF/LoRA combination and can reject execution locally.

See `docs/architecture/STREAM_COHOST_13_10.md` for the full authority/data-flow contract.
