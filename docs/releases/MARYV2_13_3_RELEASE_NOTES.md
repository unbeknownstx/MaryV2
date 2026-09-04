# MaryV2 13.3 — Connected Presence

Date: 2026-09-03

## Release intent

13.3 is an integration release, not a rewrite. It preserves the 13.2 canonical
Mary Core and extends the boundaries needed for Mac/iPhone/Twitch/avatar presence.

## Added

- explicit connected-session handshakes for creator surfaces and capability nodes;
- deterministic stream response-channel planner (react/chat/speak/both/wait/drop);
- Twitch EventSub lifecycle/reconnect state contract;
- bounded outbound Twitch chat planner with approved channels, dedupe, reply IDs,
  rate headroom, and self-echo detection;
- streaming-coordinator self-author suppression;
- Twitch reply-thread normalization;
- canonical display text + separate deterministic spoken/TTS text in performance
  packets;
- offline `scripts/check_mac_13_3.py` readiness report;
- 13.3 research synthesis documenting adopted and rejected external patterns.

## Changed

- active Core/server/node/task/feedback architecture identity advanced to 13.3;
- mobile web and bundled iOS web surface advanced together to 13.3;
- iOS marketing/build metadata advanced to 13.3 / 133;
- desktop presentation now prefers canonical response text for display while using
  the spoken variant for TTS.

## Preserved invariants

- one Mary Core owns canonical identity and state;
- capability nodes remain replaceable compute/tool providers;
- Twitch/social input remains untrusted environment context;
- creator speech owns the conversational floor;
- local FastBrain can rank but cannot authorize tools or durable state changes;
- canonical text/history is not silently overwritten by TTS pronunciation cleanup;
- no Twitch credentials are persisted into Mary memory/relationship state.

## Validation

Validated in the build environment on 2026-09-03:
- full deterministic pytest: **1,616 passed, 1 skipped**;
- release hygiene: PASS;
- repository structure: PASS;
- MaryV2 convergence: PASS;
- `mobile_web` and bundled native `www` parity: PASS;
- 13.3-specific Twitch/streaming/handshake/performance tests: PASS.

The aggregate offline release runner completed its embedded full pytest phase
green but exceeded the build environment execution cap while continuing through
its long milestone-verifier chain, so no aggregate PASS is claimed from that
runner. Physical Mac/Xcode, Metal/llama.cpp, production Railway, Twitch OAuth/
EventSub, and iPhone acceptance remain hardware/network gates and cannot be
truthfully certified by a Linux build environment.
