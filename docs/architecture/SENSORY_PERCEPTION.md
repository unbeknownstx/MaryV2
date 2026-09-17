# MaryV2 Sensory Perception — Eyes and Ears

Mary's perception is one capability fabric shared by iPhone, Windows, Mac, browser, Creator Lab and future streaming surfaces. A surface is a sensor/body endpoint; it is never another Mary.

## Pipeline

capture -> local change/VAD gate -> authorized capability -> objective observation -> PerceptionDirector -> AttentionBus -> Mary cognition -> optional memory promotion/action

Raw pixels/audio do not become identity or memory. Perception providers describe; Mary interprets.

## Eyes

Supported/target sources share the same contract: selected photos, camera frames, desktop/window screenshots, browser context, game/video frames and creator artwork. Existing `sensor.screen_describe` remains the semantic screen capability. Creator Lab uses the same contract for selected images.

A file reference alone never means Mary saw it. A real perception result is required before Mary can claim visual knowledge of the asset.

## Ears

Microphone speech, approved system audio and media transcripts enter as audio/speech observations. VAD/change detection should run near the device so silence and repeated audio are not continuously shipped to models. Speech addressed to Mary remains distinct from ambient/media audio.

## Attention

`SensoryAttentionController` provides the cheap first gate. Duplicate frames are ignored. Meaningful scene changes, explicit creator requests, or Mary's own inspection requests can trigger deeper perception. This avoids continuously sending full desktop/camera video through a VLM.

## Privacy and permissions

Sensor access is mode- and surface-bounded. Camera must never become ambient merely because another sensor is enabled; live camera requires explicit surface consent. Screen/system-audio capture must show a visible live state and obey the device capability permission layer. Private creator memory is not projected into public/stream perception.

## Memory boundary

Observations are ephemeral `environment_context_only` by default. Seeing a frame does not automatically create durable memory. Existing memory/learning policy decides whether a meaningful event later becomes episodic/semantic evidence.

## Creative loop

selected image -> vision.describe -> grounded Creator Lab asset -> canonical Mary caption/reaction/script -> canonical delivery plan -> Mary voice -> optional image/video production -> review -> Social Studio/Gallery/project -> explicit publish

The same loop works on desktop with a selected file or current-window observation.

## Streaming loop

game/window frames + system audio + microphone + chat -> attention -> bounded observations -> Mary reaction -> voice/avatar/OBS. The streamer is therefore the same Mary receiving public sensory context, not a separate VTuber chatbot.
