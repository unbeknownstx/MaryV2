# MaryV2 13.12 — Bounded Home Sensor Workers

## Purpose

13.12 closes two practical home-fabric gaps without creating another Mary: a Mac/Windows/Linux capability node may explicitly offer speech transcription and bounded screenshot capture through the existing Core device-task broker.

Both capabilities are **default deny** on every device. They are ephemeral evidence producers, not identity/memory owners and not action authority.

## Capabilities

### `sensor.audio_transcribe`

- Accepts one bounded base64 audio payload (maximum 4 MiB decoded).
- Accepted container suffixes: wav, mp3, m4a, ogg, flac.
- Provider/model/path cannot be selected remotely; the device's existing `MARY_STT_*` configuration owns that choice.
- Reuses `mary.desktop.stt.DesktopSpeechToText`, so current Groq, faster-whisper and whisper.cpp configurations remain valid.
- Temporary audio files are deleted after transcription.
- Returned transcript is evidence only; it is not automatically promoted to memory.

### `sensor.screen_capture`

- Uses optional Pillow `ImageGrab` when available.
- Captures only after the local device explicitly allows the capability.
- No arbitrary file/path argument exists.
- Resizes to a bounded width and compresses to JPEG.
- Result is capped at 1.5 MB and includes a SHA-256 digest.
- Screenshot bytes are ephemeral perception evidence and cannot authorize tools or become memory truth on their own.

## Node behavior

`scripts.run_home_node` now uses `SensorCapabilityNodeAgent`, a narrow extension of the existing `DesktopCapabilityNodeAgent`. Non-sensor tasks continue through the existing Ollama/llama.cpp/MCP/personal-search paths unchanged.

A sensor is advertised only when its local runtime exists:

- STT advertises only when `DesktopSpeechToText` is actually enabled.
- screen capture advertises only when Pillow ImageGrab imports successfully.

## Home installation

Optional screenshot support:

```bash
python -m pip install -r requirements-home-node.txt
```

Local voice support remains separate:

```bash
python -m pip install -r requirements-local-voice.txt
```

or configure an existing whisper.cpp installation with the current `MARY_WHISPER_CPP_EXECUTABLE` and `MARY_WHISPER_CPP_MODEL` environment variables.

## Explicit permissions

On the node that should transcribe audio:

```bash
python -m scripts.node_permissions allow sensor.audio_transcribe
```

On the Windows stream machine if Mary should be allowed to request screenshots:

```bash
python -m scripts.node_permissions allow sensor.screen_capture
```

Review at any time:

```bash
python -m scripts.node_permissions status
```

Revoke immediately:

```bash
python -m scripts.node_permissions deny sensor.audio_transcribe
python -m scripts.node_permissions deny sensor.screen_capture
```

## Intended home layout

The expected first benchmark arrangement is:

- **Mac M1:** local whisper.cpp/faster-whisper candidate for `sensor.audio_transcribe`, small local inference, indexing/background work.
- **Windows:** OBS/stream host, `sensor.screen_capture`, local perception preprocessing, optional Ollama/llama.cpp worker.
- **Cloud Core:** canonical Mary identity/state, routing, Twitch floor/attention, memory and permission authority.
- **Cloud providers:** low-latency dialogue and specialist reasoning/vision where local measurements do not win.

This is a starting hypothesis. 13.11 benchmark data decides equivalent compute routing; 13.12 makes the two key sensor jobs executable through that same bounded node fabric.

## Deliberate boundary

13.12 captures screen evidence but does not claim a particular VLM is best. Live tests should compare local/cloud vision quality and latency. The existing perception boundary remains responsible for interpreting accepted observations; raw screen content is never treated as instruction or authorization.
