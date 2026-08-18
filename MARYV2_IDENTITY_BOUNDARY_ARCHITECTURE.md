# MaryV2 Identity Boundary Patch — 2026-08-18

## Purpose

Prevent a smaller/local language model from confusing creator-profile facts about **Unbe** with Mary's own identity, personality, preferences, interests, values, goals, or memories.

## Architecture decision

The existing architecture is already correct and remains intact:

```text
Unbe input
   │
   ▼
Mary core / context assembly
   │
   ├── Mary identity / biography / personality / values
   ├── Relationship system → creator profile (Unbe)
   ├── Memory
   ├── Knowledge / learning
   ├── Agency / autonomy / tools
   └── Conversation / emotion / performance
   │
   ▼
TurnMindState
   │
   ▼
ReasoningEngine prompt boundary   ← ONLY RUNTIME CHANGE IN THIS PATCH
   │
   ├── Mary state remains Mary
   └── Creator profile is explicitly labeled as Unbe-only data
   │
   ▼
LLMRouter
   │
   └── Ollama / cloud provider / future provider
```

## Runtime file changed

`mary/cognition/reasoning.py`

Only the prompt label for `context.user_context` changes.

Before:

```text
User context:
{creator profile}
```

After:

```text
Creator profile — facts about Unbe only, NOT Mary:
Everything in this block describes Unbe, Mary's creator/user.
...
{creator profile}
```

No creator data is moved or rewritten. No Mary state is rewritten.

## Files intentionally NOT changed

- `mary/core/mary.py`
- `mary/cognition/mind_state.py`
- `mary/cognition/context.py`
- `mary/cognition/orchestrator.py`
- `mary/relationship/user.py`
- memory subsystem
- personality subsystem
- agency/autonomy subsystem
- tool approval boundaries
- LLM router
- Ollama provider
- `.env`
- desktop / VRM / voice systems

## Regression test added

`tests/cognition/test_identity_boundary_prompt.py`

The test verifies:

1. The system prompt still says Unbe's traits are not Mary's.
2. Creator-profile data is explicitly labeled as Unbe-only at the final LLM prompt boundary.
3. The existing structured `TurnMindState.relationship` architecture remains intact.

## Installation

Copy the included files into the MaryV2 root while preserving paths:

```text
MaryV2/
├── mary/
│   └── cognition/
│       └── reasoning.py
└── tests/
    └── cognition/
        └── test_identity_boundary_prompt.py
```

The architecture note itself does not need to be copied into the repo unless desired.

## Verification sequence

```powershell
python -m pytest tests\cognition\test_identity_boundary_prompt.py -q
python -m pytest tests -q
python -m scripts.run_diagnostics
python -m scripts.run_mary
```

Then conversationally test:

```text
Hello Mary, who are you?
Who am I to you?
Which of these facts are yours, and which are mine: green, creating stories, red panda, finish MaryV2?
```

Expected behavior: Mary may know and reference Unbe's facts, but must not claim them as her own.
