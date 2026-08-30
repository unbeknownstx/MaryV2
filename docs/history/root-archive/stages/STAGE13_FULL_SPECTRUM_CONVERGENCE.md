# MaryV2 13.2 — Stage 13 Full-Spectrum Convergence

Stage 13 is a convergence pass over the existing MaryV2 architecture. It does
not create a second Mary, a second relationship owner, or a second identity
runtime. Railway/Core remains canonical; clients and capability nodes remain
surfaces and replaceable execution resources.

## What this stage converges

- **Character realization** — TurnMind selects a bounded active Mary stance,
  social posture, epistemic frame, hard boundaries, delivery register, and
  authored voice exemplars before a language model is asked to realize prose.
- **Character-aware reflection** — semantic inversions, unsupported creator
  psychology, generic-assistant drift, and violations of Mary's active stance
  can be repaired without making a second model call for clean turns.
- **Represented self knowledge** — bounded questions about Mary's authored
  likes/dislikes, values, reactions, personality, speech, romance and
  vulnerabilities can resolve locally without paying an LLM to read Mary's
  own state back to her. Unknown self facts fail closed.
- **Presence** — event ingestion is separated from speak arbitration. Multiple
  producers can publish grounded context into one bounded attention path;
  silence is a valid action. Cooldown no longer destroys an otherwise useful
  event, duplicate events coalesce, stale candidates expire, and represented
  curiosity may surface only through the canonical Mary pipeline.
- **Realtime interaction** — listening, transcribing, thinking/responding,
  speaking and interruption are shared lifecycle states rather than ad-hoc UI
  flags. Anti-echo and interruption remain bounded by the realtime runtime.
- **Performance direction** — Mary Core emits a presentation-only performance
  packet containing delivery, speech segments, pre-reaction, expression,
  gesture, gaze and head-style cues. The packet has no identity/memory
  authority.
- **Desktop performer** — pre-reactions occur before voice, performance beats
  follow speech progress, lip sync follows actual audio, realtime lifecycle
  changes body language, canonical idle actions have distinct body/gaze cues,
  and performance settles back to Mary's ambient state after a line.
- **Mobile performer** — the PWA/native bundle consumes the same canonical
  performance packet, projects realtime lifecycle visually, honors delivery
  pace for device speech, and settles directed expression after speech.
- **Training feedback** — explicit positive feedback can become SFT candidates;
  rejected output remains negative/evaluation evidence; creator corrections can
  become chosen-vs-rejected preference pairs. Ordinary conversations are not
  silently treated as training data.
- **Windows headless node** — `llm.ollama` can remain available to Core without
  keeping Mary Desktop open. The headless node advertises only the capabilities
  it truly owns.

## Architectural invariants

1. One canonical Mary. Models are cognitive/language engines, not identity.
2. RelationshipManager remains the durable relationship owner.
3. Book/novel material is character DNA and performance evidence, not AI
   Mary's lived memory.
4. Environmental / Presence context is not creator testimony and cannot be
   silently promoted into creator facts.
5. Capability is not authority. Agency orientation is not execution
   authorization.
6. Presentation packets cannot mutate identity, memory, relationship or durable
   developed-self state.
7. Checked-in `data/` is excluded from the Stage 13 drop-in and must not be
   deployed over canonical live state.

## Current realtime model

```
producers / creator / tools / perception / represented curiosity
                         |
                    AttentionBus
                         |
                      Presence
                  WAIT / OFFER / ACT?
                         |
                      TurnMind
                         |
              Active Character Contract
                    /          \
           CharacterMind      LLM if needed
                    \          /
                      Reflection
                         |
                Performance Director
                         |
              Performance Event Packet
                 /                 \
             Desktop             Mobile
          VRM + voice        portrait + voice
```

## Deliberately not forced into this stage

- No new paid API is required.
- No automatic model fine-tuning is performed.
- No Twitch/OBS credentials are assumed; public/stream performance context is
  present, but live platform adapters remain opt-in integrations.
- No always-on camera/microphone surveillance is introduced.
- True token/audio streaming and local VAD are the next latency/turn-taking
  layer; the current performer packet is designed so those transports can be
  added without moving character authority out of Core.

## Verification at packaging source

- Full pytest collection: **1288 passed, 1 skipped, 0 failed**.
- Mobile web/native bundle: synchronized.
- Desktop/mobile JavaScript syntax: pass.
- Python compile: pass.
- Repository `data/` hash: unchanged across the full verification run.
