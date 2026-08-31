# MaryV2 CharacterSourcebook Active Pack

This is the **native live-sourcebook projection** of Mary Character Authority Alpha.

Copy/merge the `character_sources/active/` directory into the root of the current MaryV2 repository.

The existing MaryV2 `CharacterSourcebook.from_environment()` will discover these files automatically when
`MARY_CHARACTER_SOURCES` is not overriding the default path.

Live files:
- mary_character_authority_alpha.jsonl
- mary_behavior_corpus_alpha.jsonl
- mary_relationship_lenses_alpha.jsonl
- mary_negative_examples_alpha.jsonl
- mary_voice_direction_alpha.jsonl

The evaluation suite is shipped at the pack root and is intentionally NOT under `active/`, so it does not
pollute Mary's live prompt evidence.

After copying, from the MaryV2 repo root run:

    python scripts/check_character_sourcebook_alpha.py

Expected:
- enabled: True
- records: > 0
- sources: 5
- source_names: the five active files
- errors: []

Then instantiate a local Mary or run the normal local tests before deployment.
