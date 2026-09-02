# Optional local VAD asset

MaryV2 can use a lightweight Silero VAD model for future continuous local voice on macOS/iOS/Windows.

Recommended source (sherpa-onnx release asset):

`https://github.com/k2-fsa/sherpa-onnx/releases/download/asr-models/silero_vad.onnx`

The model is **not required** for Mary Core or normal chat. It is a derived runtime asset and should be downloaded explicitly rather than making startup fetch external files.

Suggested path after download:

`assets/models/vad/silero_vad.onnx`

Use `scripts/fetch_optional_realtime_assets.py --silero-vad` to download and checksum it.
