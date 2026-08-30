# MaryV2 13.0 — Connected Development Evolution

MaryV2 13.0 builds directly on the working 12.13 mobile/desktop runtime. It is **not a reset** and it does not create a second Mary. The same canonical `MaryApplication` remains the owner of identity, memory, relationship, cognition, agency, tools and provider routing.

## Upgrade safely

Overlay this release on the MaryV2 project root. The release archive intentionally excludes `.env`, `data/`, virtual environments, caches and provider credentials, so your existing private state and secrets stay in place.

After overlaying, run:

```bash
python -m scripts.check_mary_13
python -m scripts.run_release_verification
```

On Replit, use the same commands in the shell. Then launch mobile with:

```bash
python -m scripts.run_mobile
```

## What is new

### Intentional Conversation Engine

Normal chat remains fast and adaptive. When you want more than a short response, Mary can hold an intentional thread across multiple turns.

Natural cues work on every client:

- `let's talk`
- `ask me some questions`
- `get to know me`
- `go deeper`
- `think this through with me`

Mary Mobile also exposes **AUTO / TALK / DEEP** controls. Engaged and Deep modes use larger reasoning/output budgets and explicitly encourage grounded initiative, continuity, opinions and one meaningful question when it advances the thread. They do not turn every reply into an interview.

Terminal shortcuts:

```text
/talk
/deep
/auto
/conversation
/growth
```

### Continuous Development Engine

Mary now has a post-turn experience/development loop instead of only collecting conversation history.

It can:

- journal bounded, observable experiences;
- consolidate meaningful structured experiences into semantic memory using the existing safe consolidator;
- detect strict, repeated preference-development evidence and promote only mature candidates;
- create grounded relationship/development milestones;
- expose development candidates and progress in Mobile → **Growth**.

Safety boundary: model-authored dialogue is context, **not evidence that Mary permanently changed**. Canonical identity/values are not silently rewritten. Durable development requires represented evidence.

### Voice Lab + natural ElevenLabs baseline

13.0 resets the default ElevenLabs tuning to a neutral baseline:

```text
stability = 0.50
similarity = 0.75
style = 0.00
speed = 1.00
speaker boost = false
```

Dynamic emotional voice shaping is now opt-in:

```text
MARY_TTS_DYNAMIC_DELIVERY=false
```

Mobile → **Voice & Avatar** includes Voice Lab. Add private voice IDs on the server-backed screen, label them, switch between them, tune one parameter at a time and use the same reference sentence for comparison. Voice IDs are not returned in the public mobile state.

### Simpler provider truth

Provider-specific model environment variables are respected. On Replit, a known-good current setup is:

```text
MARY_LLM_MODEL=openai/gpt-oss-20b
MARY_GROQ_MODEL=openai/gpt-oss-20b
```

Use:

```bash
python -m scripts.check_llm_routes --live
```

for a tiny live request to each configured free cloud provider. The diagnostic reports provider/model/status/errors without printing API keys.

## Mobile 13.0

The PWA remains installable on iPhone and still talks to the same host Mary. Protocol 3 adds Growth, conversation-mode control and Voice Lab while retaining chat, voice, STT, Command, Focus, Studio, Study, Research, Presence, Runtime and the existing workspaces.

The native iPhone web bundle is synchronized with `mobile_web/` for the later Xcode build.

## Important environment values

Keep secrets in `.env` / Replit Secrets, never in browser JavaScript.

Useful non-secret controls:

```text
MARY_CONVERSATION_MODE=adaptive
MARY_TTS_PROVIDER=auto_fast
MARY_TTS_DYNAMIC_DELIVERY=false
MARY_ELEVENLABS_MODEL=eleven_flash_v2_5
MARY_STT_PROVIDER=groq
MARY_STT_MODEL=whisper-large-v3-turbo
```

Use `python -m scripts.check_mobile_voice` to verify TTS/STT configuration without synthesizing audio.


## Environment parity

To compare non-secret configuration between machines:

```bash
python -m scripts.check_environment_parity --export mary-config.json
python -m scripts.check_environment_parity --compare mary-config.json
```

The profile contains routing/model/voice configuration only; it intentionally excludes API keys, tokens, memories and creator data.
