# MaryV2 12.11 — Fast Dialogue + Connected Presence

## Live evidence that drove this release

On the creator's Windows PC, the 12.10 runtime trace for a casual turn showed roughly:

- Groq provider call: 768 ms
- reasoning: 773 ms
- reflection/revision: 10.5 s
- ElevenLabs Flash synthesis: 324 ms

The dominant latency was therefore a second model-backed reflection/revision pass, not TTS.

## 12.11 response lanes

- `SOCIAL_INSTANT`: greetings, reactions, brief relational/casual turns.
- `CONVERSATION`: ordinary back-and-forth discussion.
- `THINKING`: analysis, debugging, planning, difficult synthesis.
- `EXPERT`: explicit specialist route with paid-resource authorization as required.

Simple safe turns use the fast conversation Groq model and can repair bounded style-only problems locally. Identity/provenance/capability-truth problems continue to require the stronger reflection boundary.

## Latency target

The first Windows live target is <2 seconds to useful text and a low-single-digit time to audible speech on simple social turns. Instrumentation must measure rather than assume success.
