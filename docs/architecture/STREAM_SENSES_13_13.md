# MaryV2 13.13 — Public Creator Voice Stream Bridge

13.13 connects creator microphone input to the existing public stream lane without creating another Mary, another conversation authority, or a private-to-public state leak.

## Data path

1. The stream host captures local microphone PCM only when `MARY_STREAM_CREATOR_HEARING=1`.
2. Existing Mary VAD logic segments one bounded utterance.
3. The utterance is encoded as WAV and dispatched through the normal capability broker as `sensor.audio_transcribe`.
4. An authorized home node performs STT using its configured local/cloud STT adapter.
5. The transcript is submitted to canonical Mary Core using the existing `stream-public` conversation and `voice_input=True`.
6. Mary Core produces the canonical response and Core TTS synthesizes presentation audio.
7. A loopback OBS Browser Source exposes only the bounded response audio/caption packet.

## Authority and privacy

- Mary Core remains the sole identity, memory, relationship and conversation authority.
- Raw continuous microphone audio is never stored as Mary memory.
- Only one bounded utterance is dispatched to an explicitly authorized STT capability node.
- The bridge cannot invoke arbitrary shell, filesystem, mouse or keyboard actions.
- Creator voice goes directly to the public stream lane; it does not mirror private Desktop conversation state.
- `realtime.voice_activity` is reported for creator-floor/barge-in coordination.

## Optional dependencies

Install `requirements-streaming-audio.txt` only on the machine capturing the creator microphone. Core startup and non-voice stream operation do not depend on it.

## Home test

After both home nodes are online and `sensor.audio_transcribe` is authorized on at least one node:

```text
MARY_STREAM_CREATOR_HEARING=1
MARY_STREAM_CONVERSATION_ID=stream-public
MARY_STREAM_VOICE_RELAY_PORT=8766
```

Run `python -m scripts.run_stream_creator_voice` beside the existing Twitch cohost. The printed loopback URL can be added as an OBS Browser Source. Benchmarking determines which node should own STT; the public conversation contract does not change when that placement changes.
