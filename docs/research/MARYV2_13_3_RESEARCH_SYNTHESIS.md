# MaryV2 13.3 Research Synthesis

Date: 2026-09-03

## Rule

Research informs Mary; it does not replace Mary. Canonical identity, memory,
relationship, developed-self state, creator authority, and durable state remain
owned by one Mary Core. External projects are architectural references only.

## Current reference systems and adopted lessons

### AIRI

Useful current direction: multi-node plugin/bridge/viewer systems, explicit
control-plane vs high-rate data-plane separation, remote and local capabilities
behind one API, and capability lifecycle/readiness gates.

Mary adoption:
- keep the existing Core as the control/state authority;
- keep high-rate realtime data ephemeral and separate;
- make connected-session identity and architecture explicit;
- continue readiness-aware capability-node routing rather than coupling Mary to
  one machine or model.

### Neuro SDK / Neuro-sama ecosystem

Useful current direction: explicit connected-character metadata, registered
actions, result acknowledgements, and urgency-aware forced actions that can wait,
shorten speech, or interrupt only when urgency requires it.

Mary adoption:
- connected-session handshake now identifies the accepted Mary Core;
- existing SpeakerScheduler/SpeechOutputArbiter remain the single speech-floor
  authority instead of adding a second action system;
- response planning records voice/chat priority without allowing social input to
  bypass creator-first floor rules.

### Open-LLM-VTuber

Useful current direction: cross-platform desktop/web companion, transparent pet
mode, backend-driven expressions, interruption/anti-echo, proactive speech,
modular ASR/TTS/LLM providers, screen/camera perception, and shared state between
presentation modes.

Mary adoption:
- preserve canonical text separately from TTS-friendly spoken text;
- strengthen self-echo suppression across both microphone and typed Twitch chat;
- keep avatar/presentation replaceable and downstream of Mary cognition;
- keep local/cloud providers interchangeable.

### Riko and smaller Neuro-inspired projects

Useful direction: keep the fast realtime loop understandable; use small/local
models for classification/reranking and expensive models only when warranted.
Several public recreations use one prioritized input path and explicit speaking
state to prevent echo/reentrancy.

Mary adoption:
- FastBrain remains ranking-only, not identity or decision authority;
- streaming attention stays deterministic at the safety/floor boundary;
- Mac llama.cpp remains a useful cheap specialist node rather than a second Mary.

## 13.3 implemented synthesis

1. **ConnectedSessionHandshake** — surfaces and capability nodes receive explicit
   Core instance, architecture, protocol, peer kind, and state-authority truth.
2. **Twitch EventSub session state machine** — welcome/keepalive/notification/
   reconnect/revocation continuity is modeled independently of cognition.
3. **Twitch outbound chat outbox** — approved-channel gating, reply threading,
   dedupe, rate planning, bounded history, and self-message detection.
4. **Streaming response-channel plan** — Mary can deterministically choose
   DROP/REACT/CHAT/SPEAK/BOTH/WAIT after attention and creator-floor decisions.
5. **Typed-chat self-echo guard** — Mary's own bot user ID can never re-enter the
   streaming attention loop.
6. **Reply-thread preservation** — Twitch parent/thread IDs survive normalization.
7. **Display vs spoken text split** — canonical text remains visible/history truth;
   deterministic TTS rendering can differ without rewriting Mary's response.
8. **13.3 surface convergence** — Core/node runtime identities, mobile web bundle,
   bundled native web client, and iOS metadata advance together.
9. **Mac readiness checker** — safe offline check for desktop/native/toolchain/local
   model/Core configuration prerequisites.

## Deliberately not imported

- No external project's persona or memory model.
- No second identity/state authority on Mac, Windows, Twitch, avatar, or mobile.
- No autonomous Twitch network writes without explicit credentials/configuration.
- No uncontrolled screenshot/keylogging/computer-use loop.
- No model-generated durable relationship truth.
- No new dependency on Live2D, VRM, Unity, Unreal, or any one renderer.

## Next 13.3 runtime activation work on the physical Mac

The source is prepared for the next hardware-backed acceptance pass:
1. run `python scripts/check_mac_13_3.py`;
2. verify authenticated Mac surface -> production Core handshake;
3. start the Mac capability node and confirm the returned 13.3 handshake;
4. validate llama.cpp/Metal as a specialist capability;
5. build/run the native iOS project with Xcode and validate remote Core continuity;
6. configure a separate Twitch bot OAuth identity only when ready for live Twitch
   acceptance;
7. connect avatar/OBS presentation after Core/streaming continuity is green.
