# MaryV2 Character Sourcebook

`CharacterSourcebook` is the bridge from creator-authored Mary material into the live runtime.
It does **not** replace Character Core, memory, relationship state, or developed self.

## Configure

On Windows, point Mary at one or more authored source files/directories:

```powershell
$env:MARY_CHARACTER_SOURCES = "C:\MarySources\Mary_Definitive_Character_Bible.docx;C:\MarySources\Mary_Corpus.md"
python -m scripts.check_mary_character_authority
```

For permanent local configuration, use the same variable in your private `.env`. Do not commit the
private `.env`.

Supported source formats:

- `.docx` (read directly; no manual conversion required)
- `.md`
- `.txt`
- `.json`
- `.jsonl`

## Evidence labels

The runtime preserves the creator workbook labels:

- `FC`: fictional canon/reference, never automatically AI Mary's lived memory
- `DNA`: shared Mary character DNA
- `AI`: authored persistent-AI-Mary material
- `PUB`: public/performer context for the same Mary
- `ALT`: alternate/experimental interpretation
- `NEG`: anti-example, explicitly not behavior to imitate

Unlabeled material remains usable as `UNSPECIFIED` authored evidence but is weighted lower than
explicit DNA/AI material.

## Context behavior

The sourcebook can be very large. The model does not receive the whole sourcebook. Each turn gets a
small deterministic retrieval set, with source name, label, provenance boundary, and content hash.

This enforces the MaryV2 rule:

> Everything may be addressable without everything being in the prompt.

## Authoring rule

Keep the filled Bible human-readable and expressive. Do not reduce it to JSON traits by hand. The
sourcebook is designed to consume the authored material and derive bounded machine context from it.
