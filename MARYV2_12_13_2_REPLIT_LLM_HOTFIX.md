# MaryV2 12.13.2 — Replit LLM Routing Hotfix

This is a small overlay patch for the current MaryV2 12.13 mobile build. It does **not** contain `.env`, API keys, `data/`, memories, relationship state, voice credentials, or mobile access tokens.

## Fixes

1. **Groq provider-specific model override now wins**
   - `MARY_GROQ_MODEL` is honored even when `MARY_LLM_PROVIDER=groq`.
   - This fixes the mismatch where `echo $MARY_GROQ_MODEL` could show one model while Mary's route checker/runtime instantiated another.

2. **Groq short-conversation model no longer silently ignores `MARY_GROQ_MODEL`**
   - Precedence for social/fast conversation is now:
     1. `MARY_GROQ_CONVERSATION_MODEL`
     2. `MARY_GROQ_MODEL`
     3. legacy `MARY_LLM_MODEL` when Groq is primary
     4. built-in fallback

3. **Classifier/safety-label leakage is rejected before it reaches Mary**
   - Responses like `User Safety: safe` are treated as invalid provider output and trigger normal failover instead of being displayed as Mary's dialogue.

4. **Route checker now has a live diagnostic mode**
   - `python -m scripts.check_llm_routes` remains configuration-only and spends no LLM quota.
   - `python -m scripts.check_llm_routes --live` makes one tiny request to each configured free cloud provider and prints sanitized error/status information without printing API keys.
   - The checker separately reports Mary's task route and chat route and shows a separate Groq chat model when applicable.

5. **12.13 mobile verifier is registered in the release gate**
   - Fixes the source-snapshot test that detected `scripts.verify_mobile_12_13` but did not find it in the verifier registry.

## Files replaced / added

- `mary/llm/router.py`
- `mary/llm/output_quality.py`
- `scripts/check_llm_routes.py`
- `scripts/run_release_verification.py`
- `tests/llm/test_replit_provider_config_hotfix.py` (new)
- `tests/llm/test_output_quality.py`

## Install

Extract this archive over the **root of the current MaryV2 repository**, preserving directories. It intentionally does not touch any mobile voice/iOS hotfix files.

Commit/push the changed files to GitHub, pull them into Replit, then fully restart the Mary process.

## Replit verification

Configuration-only:

```bash
python -m scripts.check_llm_routes
```

Then run the live diagnosis:

```bash
python -m scripts.check_llm_routes --live
```

The live check is intentionally small but does make provider requests. It redacts configured API-key values from errors.

For the focused deterministic tests:

```bash
python -m pytest tests/llm/test_replit_provider_config_hotfix.py tests/llm/test_output_quality.py -q
```

Then restart mobile:

```bash
python -m scripts.run_mobile
```

## Verification performed when this patch was built

- Focused LLM/router tests: **36 passed**
- Full deterministic suite after the registry cleanup: **760 passed, 1 skipped**
- Diagnostics: **54/54 PASS**
- Full offline release verification: **PASS**

No live provider request was made while building this patch, because the build environment does not contain the user's provider credentials. The `--live` command on Replit is the intended next diagnostic if a provider still fails.
