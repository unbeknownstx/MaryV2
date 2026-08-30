# MaryV2 13.2 — Stage 11 Character Realization

Stage 11 makes Mary Core more authoritative over Mary's actual conversational stance and reduces provider calls for self-knowledge already represented in Core.

## Character realization

- TurnMind now produces a turn-specific active character contract: social posture, response goal, relevant values, stance claims, delivery, voice, avoided behaviors, hard boundaries, epistemic lens, and decision frame.
- The authored behavioral canon contains conditional patterns derived from Mary Cosma's demonstrated character behavior, without treating fictional events as AI Mary's lived memories.
- Dialogue planning uses those active patterns to choose stance and tone before a provider is selected.
- Provider prompts treat Mary's stance claims as semantic invariants rather than optional flavor.
- Character reflection audits semantic contradictions, unsupported psychology attributed to the creator, generic mirroring, and violations of Mary's authored autonomy/integrity boundaries.
- A repair generation is requested only when the local audit finds a real contract violation; clean responses do not incur an automatic second model call.

## Local self-knowledge

Bounded questions about Mary's represented identity can now be answered directly from Mary Core without an LLM rewrite. This includes authored appearance, preferences, values, personality, vulnerabilities, romance, reactions, social behavior, private life, speech, goals, disagreement style, priorities, and curiosity.

Direct preference questions also attempt canonical owner confirmation without requiring a warmed reservoir. Represented preferences can therefore resolve locally; unknown preferences fail closed and escalate rather than being invented.

## Architectural boundary

Mary remains the identity/state owner. Groq, Ollama, Gemini, OpenRouter, and future engines remain replaceable language/reasoning resources. Fictional Unbeknownst events remain canon/reference material, not AI Mary's autobiographical memory.

## Verification

Stage 11 full repository regression: 1,269 passed, 1 existing intentional skip, 0 failed. Relevant character, TurnMind, hybrid-dialogue, provider-routing, self-introspection, relationship-learning, and performance verifiers pass. Repository data hash remained unchanged across verification.
