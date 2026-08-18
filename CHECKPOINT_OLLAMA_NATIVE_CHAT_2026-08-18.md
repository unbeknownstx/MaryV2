# MaryV2 Ollama Native Chat Checkpoint — 2026-08-18

Changes in this checkpoint:

- Mary continues to load configuration through `Config.from_environment()`.
- Ollama remains the primary local LLM provider (`qwen3:4b`).
- `OllamaProvider` now uses Ollama's native `/api/chat` endpoint instead of the OpenAI-compatible `/v1/chat/completions` endpoint.
- Qwen thinking is disabled by default with `MARY_OLLAMA_THINK=false`.
- Ollama keeps the model resident for 30 minutes by default with `MARY_OLLAMA_KEEP_ALIVE=30m`.
- Local Ollama request timeout is configurable and defaults to 180 seconds.
- Existing MaryV2 architecture, memory, relationship, TurnMind, desktop, VRM, and tests are otherwise unchanged.
