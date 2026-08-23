# OpenAI Expert Route — MaryV2 12.11

OpenAI remains an **optional specialist**, not Mary's normal conversational identity.

## Normal policy

- Fast dialogue: free/fast conversation route.
- Deep reasoning: existing task/deep-thinking route.
- Private/offline: Ollama.
- Paid expert: OpenAI only when the task explicitly permits paid expert use.

The existing expert bridge packages bounded task context, asks a specific specialist question, records the answer as task-local advisory evidence, and then Mary evaluates/synthesizes the result as Mary.

## Configuration

```env
OPENAI_API_KEY=<private key>
MARY_OPENAI_MODEL=gpt-5.6-luna
```

The key must remain in `.env` or another private host environment and must never be committed or packaged.

The $10 API balance is therefore a reserve for hard tasks, verification, or explicit expert consultation; routine chat should not consume it.
