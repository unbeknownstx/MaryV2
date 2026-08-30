# MaryV2 Ollama Checkpoint — 2026-08-18

Purpose: make the existing Ollama integration the active local LLM path without redesigning MaryV2.

Changes in this checkpoint:
- `mary/core/mary.py`: Mary now loads `Config.from_environment()` at startup.
- `mary/llm/router.py`: `model_name()` resolves the active provider before reporting the model.
- `.env`: sanitized local-test configuration selects `ollama`, `qwen3:4b`, and disables LLM fallbacks for the clean test. API key values are intentionally blank in this checkpoint archive.

Local test order:
1. Ensure Ollama is running and `ollama list` shows `qwen3:4b`.
2. `python -m pytest tests -q`
3. `python -m scripts.run_diagnostics`
4. `python -m scripts.run_mary`

Expected Mary startup:
- `LLM Provider: ollama`
- `LLM Model: qwen3:4b`
