# Local GPT-SoVITS Voice for Mary

Mary can use the official GPT-SoVITS v2 HTTP inference server as an optional
local voice renderer. It does not become Mary's identity, memory, emotion
authority, or dialogue engine. The canonical DeliveryPlan still determines
pace/performance; GPT-SoVITS only renders audio.

## Safety boundary

Mary's adapter accepts only loopback endpoints:

- `http://127.0.0.1:9880`
- `http://localhost:9880`
- `http://[::1]:9880`

A remote hostname is rejected. The adapter makes no request on import or Core
startup. It calls `POST /tts` only when speech is explicitly synthesized.

## GPT-SoVITS side

Use the official RVC-Boss/GPT-SoVITS repository and its `api_v2.py`. A common
local launch is:

```
python api_v2.py -a 127.0.0.1 -p 9880 -c GPT_SoVITS/configs/tts_infer.yaml
```

Configure Mary with a reference clip that the GPT-SoVITS process can read:

```
MARY_TTS_PROVIDER=gpt_sovits
MARY_GPT_SOVITS_URL=http://127.0.0.1:9880
MARY_GPT_SOVITS_REF_AUDIO=C:\MaryTools\GPT-SoVITS\references\mary.wav
MARY_GPT_SOVITS_TEXT_LANG=en
MARY_GPT_SOVITS_PROMPT_LANG=en
MARY_GPT_SOVITS_PROMPT_TEXT=<the exact transcript of the reference clip>
MARY_GPT_SOVITS_VOICE_LABEL=Mary local
```

Alternatively keep `MARY_TTS_PROVIDER=local_first` and set:

```
MARY_GPT_SOVITS_ENABLED=true
```

Then GPT-SoVITS is tried as the high-quality local renderer and Mary retains a
platform-local fallback when one is available.

## Contract

The adapter follows the official v2 `/tts` fields: text, language, reference
audio, prompt text/language, split method, speed factor, WAV media type and
non-streaming response. Provider errors degrade voice only; they do not fail a
Mary conversation.

Reference: https://github.com/RVC-Boss/GPT-SoVITS/blob/main/api_v2.py
