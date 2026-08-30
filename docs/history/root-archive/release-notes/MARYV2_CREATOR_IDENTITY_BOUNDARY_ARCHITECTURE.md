# MaryV2 Creator / Self Identity Boundary

## Goal

Keep Mary and Unbe distinct without changing Mary's memory, relationship storage,
TurnMindState, agency, autonomy, tools, Ollama provider, desktop, avatar, or voice.

## Runtime flow

```text
User input
   |
Mary core
   |
Context + memory + relationship model
   |
TurnMindState
   |-- Mary self state: identity / biography / personality / values / character
   `-- Unbe creator state: relationship.current_profile / user_context
   |
Reasoning prompt boundary
   |-- explicitly labels creator profile as ABOUT UNBE, NOT MARY
   |
LLM drafts Mary's dialogue
   |
Reflection local audit
   |-- generic-assistant audit
   |-- continuity audit
   `-- creator/self ownership audit
           |
           | clean -> accept
           |
           ` violation -> existing LLM revision path
                          |
                          | corrected -> use revised Mary dialogue
                          |
                          ` still wrong / unavailable / empty
                                -> deterministic identity-safe fallback
```

## What changed

### `mary/cognition/reasoning.py`
The existing `user_context` prompt block is explicitly labeled as Unbe's creator
profile. The model is told not to adopt its facts, preferences, interests, values,
goals, communication traits, memories, or records as Mary's own.

### `mary/cognition/reflection.py`
Adds a deterministic creator/self ownership audit. It compares creator-profile
values against Mary's drafted response and flags cases where the wording assigns
an Unbe-only value to Mary or uses an unattributed creator value to answer a
Mary-self question.

Self-introspection still reuses its grounded one-call path when clean. If a
boundary violation is found, Mary's existing revision path is used. The revised
reply is audited again. If the model still blurs ownership, or revision is
unavailable/empty, a local identity-safe fallback is returned instead.

## What did NOT change

- `mary/core/mary.py`
- memory storage or retrieval
- relationship/user model storage
- `mary/cognition/mind_state.py`
- TurnMind architecture
- agency / autonomy
- tool approval boundaries
- LLM router
- Ollama provider or `.env`
- desktop / VRM / avatar
- STT / TTS / voice

## Regression coverage

`tests/cognition/test_identity_boundary_prompt.py`
- creator profile is explicitly labeled at the reasoning prompt boundary

`tests/cognition/test_creator_identity_boundary_reflection.py`
- catches creator favorite color claimed as Mary's
- allows correct attribution of the same favorite color to Unbe
- catches creator interest claimed in first person
- catches creator fact folded into Mary's self-description
- preserves zero-extra-call self-grounding when clean
- routes creator bleed into the existing revision path
- uses identity-safe fallback if revision is unavailable
- re-audits model revisions and replaces a still-bad revision locally

## Validation performed

- focused identity/reflection/performance/self-introspection tests: 40 passed
- full offline suite excluding the live Ollama integration test: 309 passed
- diagnostics: 41 passed / 0 warnings / 0 failures / Healthy: True

The live Ollama test must be run on the user's Windows machine because this
validation environment does not have the user's local Ollama server.
