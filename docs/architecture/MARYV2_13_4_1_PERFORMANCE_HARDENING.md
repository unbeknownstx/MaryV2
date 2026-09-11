# MaryV2 13.4.1 — Stream / Affect / Presentation Hardening

This tranche adopts useful AI-VTuber patterns without introducing a second
canonical Mary.

## Added

- Unified `PresentationSessionManager`: one output-session id covers TTS,
  captions, mouth motion, avatar speaking state and stream overlays. Barge-in
  invalidates all old presentation effects.
- `StreamInputGovernor`: prompt-injection/spam/hostile-bait filtering,
  ephemeral viewer cooldowns, recently-answered cache hooks, and ignored-chat
  texture summaries before Presence/Attention.
- `StandingAffectStore`: decaying valence/arousal residue persisted across
  restarts and blended lightly into the existing emotional state. Person
  attribution requires high confidence and never mutates relationship state.
- `SerializedRequestReplyTransport`: adapter-level request/reply locking for
  VTube Studio-style shared WebSockets.
- `normalized_mouth_level`: keeps whispers visually smaller than loud speech.
- `StreamCapabilityCatalog`: OBS, VTube Studio, desktop-audio and Minecraft
  capability names subordinate to NodeRegistry/Core.

## Ownership rules

- Mary Core remains sole identity/cognition authority.
- EmotionManager remains immediate emotion authority; StandingAffect is derived
  presentation continuity only.
- RelationshipManager remains durable relationship authority.
- AttentionBus and SpeakerScheduler/SpeechOutputArbiter keep their existing
  ownership boundaries.
- Nodes execute bounded capabilities only; they never receive ownership of Mary
  state.
- Stream chat remains untrusted environment context and can never authorize a
  tool or become creator input.

## Privacy

Standing affect stores bounded numeric residue and source/cause labels only.
Canonical Mary passes a generic `conversation_appraisal` cause label; raw user
turn text is not persisted into this derived store.

## Verification

Run the targeted tests in `tests/realtime`, `tests/streaming`,
`tests/expression`, and `tests/avatar`, then the full deterministic release
gate before merging or deployment.
