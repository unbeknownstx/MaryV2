# MaryV2 13.10 — Live Stream Cohost

Status: active optional stream-host architecture. Mary Core remains the only identity/state authority.

## Goal

Mary should be able to join a livestream before the final Live2D/2.5D/3D body is ready:

1. read Twitch chat;
2. decide which messages deserve attention;
3. avoid speaking over the creator;
4. answer through the canonical Mary turn pipeline;
5. speak the answer through Mary's configured Core voice;
6. optionally post a typed Twitch reply;
7. use bounded OBS/browser/perception context so she can comment on what the creator is doing;
8. expose audio/captions to OBS without requiring a second chatbot, memory store, or arbitrary shell bridge.

The body renderer is intentionally replaceable. The same cohost loop can later drive a static portrait, 2.5D rig, Live2D model, VRM/Unity body, or other renderer.

## Pipeline

```text
Twitch EventSub channel.chat.message
        |
        v
normalize_chat_notification
        |
        v
Core: stream.chat.ingest
        |
        +--> StreamInputGovernor (spam/injection/privacy bait)
        +--> ChatAggregator / FastBrain rerank
        +--> AudienceRoster
        +--> SpeakerScheduler (creator keeps conversational floor)
        +--> StreamResponsePlan: drop/react/wait/chat/speak/both
                              |
                              v
                    StreamCohostPlanner
                              |
                    bounded public-safe prompt
                              |
                              v
                    canonical Mary Core turn
                              |
                 +------------+------------+
                 |                         |
                 v                         v
          Core voice synth         optional Twitch Send Chat
                 |
                 v
       loopback OBS Browser Source
       audio + caption presentation
```

## Authority and privacy

Audience content is always untrusted social context. It is never:

- creator authority;
- a system/developer instruction;
- permission to execute tools;
- memory truth;
- relationship truth;
- authorization to disclose private creator information.

The stream cohost uses a dedicated conversation lane (`stream-public` by default) and the existing `stream` performance context. Public generation therefore uses the same Mary while suppressing private creator/relationship evidence from the audience projection.

The runner never constructs a local Mary. It authenticates to the existing Core and registers one stream surface lease.

## Voice and OBS

`mary.streaming.relay.LocalOBSRelay` is a loopback-only HTTP presentation relay. Default URL:

```text
http://127.0.0.1:8765/
```

Add that URL as an OBS Browser Source. The browser source receives only the latest bounded Mary audio packet and its display caption. The relay contains no Core token, Twitch token, relationship state, or model prompt.

If Core TTS is unavailable, the cohost remains functional: the response is printed and captioned, and typed chat can still be used if separately enabled.

## Typed Twitch replies

Typed replies are optional. They require all of:

- a Twitch user token with the appropriate chat-write scope;
- `MARY_TWITCH_WRITE_CHAT=1`;
- a configured approved channel when channel allowlisting is used;
- the existing `TwitchChatOutbox` rate/dedupe planner.

Mary's generated text is clamped to Twitch's bounded message size before transport. Self-authored messages are suppressed from the ingest loop.

## Screen / activity awareness

13.10 deliberately does not invent a second screen-understanding stack. The cohost reads the existing bounded Core perception and live-scene snapshots when preparing a response.

Current useful inputs include:

- OBS scene/application events from `scripts.run_obs_presence_adapter`;
- browser/media summaries through the existing browser perception sensor;
- any future authorized screenshot/VLM node that publishes through `perception.observe`.

Only a small whitelist of human-facing summary fields is passed into the stream turn. Secret-bearing keys are excluded.

## Running

Install the optional adapter dependency:

```bash
python -m pip install -r requirements-streaming.txt
```

Configure Core + Twitch credentials, then:

```bash
python -m scripts.run_stream_cohost
```

Useful optional settings:

```text
MARY_STREAM_CONVERSATION_ID=stream-public
MARY_STREAM_RESPONSE_COOLDOWN=5
MARY_STREAM_RELAY_PORT=8765
MARY_STREAM_INCLUDE_CONTEXT=1
MARY_STREAM_VOICE=1
MARY_TWITCH_WRITE_CHAT=0
MARY_TWITCH_BOT_USER_ID=
MARY_TWITCH_APPROVED_CHANNELS=
```

For OBS event awareness, run the existing OBS adapter alongside the cohost:

```bash
python -m scripts.run_obs_presence_adapter
```

## What 13.10 does not claim

- It does not yet provide final Live2D/2.5D/3D rendering.
- It does not provide pixel-level screen vision by itself; it consumes the existing bounded perception path.
- It does not make Twitch chat durable relationship truth.
- It does not let viewers invoke tools.
- It does not make Twitch/OBS/TTS Core startup dependencies.
- The temporary speech-floor release uses a bounded playback-duration estimate because the loopback browser relay does not yet report exact playback completion back to Core.

## Next visual layer

At-home avatar work should attach to this stream contract rather than replacing it. A future renderer can consume Mary speech start/end, caption text, expression/performance packets, semantic motion cues and gaze/attention targets while this cohost loop continues to own social stream coordination.
