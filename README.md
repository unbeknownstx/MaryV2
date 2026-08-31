# Mary Character Authority Alpha

**Version:** 0.1.0-alpha

A living synthesis package for MaryV2 built from the current filled character-bible material, the full Unbeknownst Book 1 manuscript, MaryV2 identity-boundary decisions, and the current character-first runtime architecture.

It lets Mary use what has already been authored **now**, while remaining easy to revise as the larger bible and new scenarios are completed.

## Contents

- `human/MARY_CHARACTER_AUTHORITY_ALPHA.md` — readable synthesized authority.
- `data/mary_character_authority_alpha.json` — machine-readable weighted rules.
- `data/mary_behavior_corpus_alpha.jsonl` — generalized behavioral exemplars.
- `data/mary_relationship_ladder_alpha.json` — trust-conditioned behavior.
- `data/mary_anti_patterns_alpha.json` — Mary failure catalog.
- `data/mary_eval_suite_alpha.jsonl` — benchmark scenarios for “is this Mary?” testing.
- `data/mary_voice_bridge_alpha.json` — behavioral state → vocal intent bridge; **not final TTS tuning**.
- `data/future_additions_template.jsonl` — append/supersede template for new authored material.
- `runtime/character_authority.py` — bounded deterministic selector/adapter.
- `runtime/INTEGRATION_NOTES_13_2.md` — how to attach this to existing `personality_context`.
- `tests/test_character_authority.py` — sanity tests.
- `RUNTIME_COMPACT_PROFILE.txt` — fallback compact context for manual testing.
- `source_manifest.json` — evidence hierarchy and canon warnings.

## Design principles

1. Raw creator material remains the source.
2. This layer is a compiler, not a replacement sourcebook.
3. Latest creator decisions outrank older plot drafts.
4. A useful old scene may remain behavioral evidence even if its plot mechanism is obsolete.
5. AI Mary grows through actual [AI] experience rather than fabricated fictional memory.
6. Retrieval is selective. Personality should not become prompt bloat.
7. Repeated vocabulary decays; behavioral mechanisms persist.

## Alpha scope

This pass focuses on **character behavior and runtime identity**. Vocalization is intentionally only bridged. The next major pass should calibrate voice-state vectors against reference audio, then connect them to ElevenLabs/TTS parameters and performance-state selection.
