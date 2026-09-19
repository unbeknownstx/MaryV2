# Mary Dataset v1

Mary Dataset v1 is a provenance-bearing export built from material Mary already
owns or that the creator explicitly approved for evaluation/training.

## Included surfaces

- `mary_character_corpus.jsonl` — all approved CharacterSourcebook records with
  labels, provenance, content hash, boundary and deterministic split metadata.
- `mary_character_training_candidates.jsonl` — AI/DNA/PUB character evidence
  that may be curated for later training.
- `mary_behavior_sft.jsonl` — only explicitly structured authored
  `Situation: ... Mary behavior: ...` records converted to chat-format SFT
  examples. Arbitrary prose is never fabricated into prompt/response pairs.
- `mary_negative_examples.jsonl` — NEG-labeled anti-examples/rubric evidence.
- `mary_character_eval.jsonl` — held-out MaryBench cases. These are not
  training data by default.
- `explicit_feedback/mary_sft.jsonl` — explicitly creator-approved positive or
  corrected response examples.
- `explicit_feedback/mary_preferences.jsonl` — creator corrections as
  chosen-vs-rejected preference pairs.
- `explicit_feedback/mary_rejected.jsonl` — explicitly negatively rated
  responses.
- `explicit_feedback/mary_eval.jsonl` — feedback-derived evaluation rows.

## Explicit exclusions

The exporter does not silently harvest:
- ordinary conversation history;
- Mary memory;
- relationship history/state;
- growth/developed-self state;
- creator profile;
- provider traces;
- private runtime diagnostics.

Fictional canon remains reference material and is never converted into AI-Mary
lived memory. NEG examples are never treated as SFT targets.

## Export

From a MaryV2 checkout:

```bash
python -m scripts.export_mary_dataset_v1
```

Default output:

```text
~/.maryv2/datasets/mary-dataset-v1/
```

If a configured `training/response_feedback.json` exists, explicit feedback is
included automatically. It can also be supplied with `--feedback`.

The manifest contains sourcebook/MaryBench fingerprints, counts, file roles and
the dataset fingerprint so later LoRA experiments can record exactly which data
version they used.


## Corpus inventory and quality gate

Before expanding or training, inspect the active creator-owned corpus:

```bash
python -m scripts.inspect_mary_corpus --root .
```

The inventory is read-only. It reports source/label balance, structured
Situation/Mary-behavior coverage, NEG/FC/ALT boundaries, exact duplicate groups,
and MaryBench category coverage. It does not create examples or promote records.

Audit an exported Dataset v1 bundle with:

```bash
python -m scripts.audit_mary_dataset_v1
```

The deterministic audit blocks malformed artifacts, cross-split example
leakage, held-out MaryBench prompt contamination, and fiction/negative records
crossing training boundaries. Duplicate groups, empty held-out splits and heavy
single-source dominance are surfaced for review.

`prepare_mary_mlx_lora` now enforces this structural audit before preparing
MLX train/valid/test files. Passing the audit still does not mean a profile has
enough examples, that the host/runtime is ready, or that training/promotion has
been authorized.

## Recommended first uses

1. Keep MaryBench held out for regression evaluation.
2. Use explicit corrected/positive feedback for dialogue SFT.
3. Use `mary_behavior_sft.jsonl` as a small creator-authored character seed.
4. Curate character training candidates before expanding SFT synthetically.
5. Construct preference data from reviewed chosen/rejected pairs for DPO/ORPO.
6. Never merge memory or relationship state into model weights merely for
   convenience; retrieve those at runtime from Mary Core.

## LoRA relationship

Dataset v1 is intentionally model-agnostic. A later adapter experiment should
record:
- base model;
- base revision/hash;
- adapter method (LoRA/QLoRA/etc.);
- third-party adapter(s) already active;
- Mary dataset fingerprint;
- held-out MaryBench result;
- latency/VRAM/runtime evidence;
- license/provenance for every third-party adapter.

A third-party reasoning/dialogue/vision adapter is a replaceable capability.
Mary-specific adapters remain subordinate to Mary Core and must be benchmarked
against the no-adapter base before promotion.


Model/adapter experiments use an append-only content-free lineage ledger. Review,
benchmark, explicit trial dispatch and terminal trial outcome are retained with
artifact/dataset/node identifiers and bounded operational metadata. Held-out
prompts and generated trial text are not written to that lineage ledger.
