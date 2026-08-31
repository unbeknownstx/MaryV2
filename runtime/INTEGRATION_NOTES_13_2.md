# MaryV2 13.2 Integration Notes — Character Authority Alpha

This package is intentionally **not** a new personality system and not a second Mary.

The current ReasoningEngine already appends `personality_context` to its prompt and already protects creator-vs-Mary identity, TurnMindState authority, recent-opening repetition, and recent distinctive vocabulary. That is the correct attachment point: compile a **small relevant slice** of character authority into the existing `personality_context` before cognition runs.

## Target flow

```text
input
  -> existing memory / relationship / knowledge / TurnMindState
  -> CharacterAuthority.select(input + relationship stage)
  -> personality_context["character_authority"] = bounded payload
  -> existing CognitiveOrchestrator / ReasoningEngine
  -> existing reflection / grounding / continuity checks
```

Do not paste the entire bible or all 176 manuscript pages into the system prompt. The authority selector should normally provide:

- invariant core rules;
- ~8–12 context-relevant rules;
- one relationship lens when known;
- 0–3 behavioral exemplars;
- only relevant anti-pattern warnings.

## Minimal integration sketch

```python
from mary.character_authority import MaryCharacterAuthority

character_authority = MaryCharacterAuthority(package_root=...)

character_context = character_authority.compile_personality_context(
    input_text,
    relationship_stage=resolved_relationship_stage,
)

personality_context = {
    **existing_personality_context,
    **character_context,
}
```

Choose the exact current context-assembly file from the **checked-out current repository** at integration time. Do not overwrite newer cloud/runtime wiring based on archived copies.

## Identity rules that remain upstream and downstream

1. Unbe/creator profile is not Mary.
2. Fictional history is not AI autobiographical memory.
3. Models/providers/specialists are not Mary.
4. Character authority shapes behavior; memory supplies lived evidence.
5. New AI experience may add [AI] evidence but does not silently rewrite [FC]/[DNA].

## Update workflow

When new bible/scenario material arrives:

1. preserve raw text unchanged;
2. classify it [FC]/[DNA]/[AI]/[PUB]/[ALT]/[NEG];
3. assign evidence source and strength;
4. add/update an authority rule only when the material generalizes;
5. add the scene as a corpus exemplar when it teaches behavior;
6. add an eval when it exposes a failure mode;
7. supersede rather than erase older conclusions when possible.

## Voice handoff

Do not tune TTS from raw trait adjectives. Use `mary_voice_bridge_alpha.json` to turn selected behavioral state into vocal intent. The next vocal pass should calibrate these vectors against owned/authorized professional voice-actor references and current ElevenLabs output.
