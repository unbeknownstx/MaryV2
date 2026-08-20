# MaryV2 Breakthrough 10 — Local Character Core / Specialist Capability Stack

Breakthrough 10 turns the routing lessons from real acceptance conversations into
an explicit system boundary instead of a collection of phrase-specific hotfixes.

The architecture is verified in both directions:

```text
TOP DOWN
creator input
  -> conservative natural-input matching
  -> deterministic intent + turn policy
  -> Mary local state / memory / relationship / emotion / continuity
  -> choose generation purpose
       personal Mary conversation -> local-first
       detached task/general work -> free cloud-first
       private override -> Ollama only
       explicit expert task -> paid OpenAI only for that task
  -> provider/tool execution

BOTTOM UP
provider/tool result
  -> output-quality guard
  -> grounding / provenance / capability-truth audit
  -> local reflection/revision policy
  -> continuity / emotion / expression
  -> completed Mary response
  -> only explicit existing persistence paths may store durable changes
```

## One Mary, multiple engines

Mary is not Ollama, Groq, Gemini, OpenRouter, or OpenAI. Those providers are
language/reasoning capabilities behind one persistent Mary runtime.

Default V2 routes:

```text
personal / relational / character conversation
    Ollama -> Groq -> Gemini -> OpenRouter

detached task / factual / technical generation
    Groq -> Gemini -> OpenRouter -> Ollama

private / offline override
    Ollama only

paid expert consultation
    OpenAI, explicit one-task authorization only
```

A temporary provider/route override still beats the default purpose policy. Paid
OpenAI can never become a sticky session provider.

## TurnPolicyEngine

`mary/runtime/turn_policy.py` is the authoritative model-purpose classifier.

It exists because the intentionally broad intent detector is not precise enough
to decide provider economics/privacy by itself. Examples:

```text
"idk i just wanna talk for a bit"
    -> personal_conversation
    -> local-first Ollama

"what do u think im actually trying to say"
    -> personal_conversation
    -> local-first Ollama

"what is a fish"
    -> task_general
    -> normal free-first task route

"write me a python function to sort a list"
    -> task_general
    -> normal free-first task route
```

The original creator text is not rewritten. Conservative normalization is used
only to understand common chat shorthand and missing punctuation.

## Conversation learning bridge

`mary/relationship/conversation_learning.py` connects explicit invitations to
Mary's real `RelationshipCuriosityDevelopment` state.

If the creator says:

```text
ask me anything
what would u actually want to know about me
you are here to learn
```

Mary asks one question from an actual unresolved relationship gap. The question
requires zero LLM calls and cannot be invented by a provider. The bridge never
asks autonomously and never writes creator facts by itself. Existing natural or
explicit relationship-learning paths remain the only writers.

## Probe/test-state boundary

Old development probes may remain in durable creator/memory state for audit and
recovery, but normal model-backed conversation must never receive them.

Breakthrough 10 applies provenance filtering before both:

- the creator profile enters model context;
- retrieved memories enter model context.

`/audit` and `python -m scripts.audit_creator_state --all` remain the supported
ways to inspect those records.

## Local model supervision stays local

Local-first does not mean "trust every Ollama sentence." Ollama output still
passes Mary's character/provenance/capability-truth/reflection layers. If a local
conversation response invents off-screen Mary history, the revision call keeps
the same `conversation` purpose, so it can be corrected through Ollama without
leaking that private conversational turn to Groq.

## Architecture contract

`mary/runtime/system_contract.py` is read-only. It does not own new Mary state.
It verifies that refactoring has not accidentally created duplicate authorities.

It checks that:

- reasoning, reflection, orchestration, execution, and expert consultation share
  one live LLM router;
- avatar/expression use Mary's authoritative emotion state;
- conversation remains Ollama-first;
- task/general remains free cloud-first;
- paid OpenAI is not a sticky route;
- background browsing remains disabled.

Use `/contract` in terminal mode to inspect the display-safe ownership map.

## Persistence boundary

Breakthrough 10 does not broaden automatic persistence.

- model dialogue is not durable creator truth;
- provider output is not durable Mary identity;
- a conversation-learning question does not create a fact;
- relationship information is stored only after an accepted creator share;
- task/expert/tool evidence remains ephemeral unless an existing explicit
  promotion path is used;
- all long-lived collections remain bounded and recoverable.

## Developer entry points

Both terminal commands now reach the same canonical runtime:

```powershell
python run_mary.py
python -m scripts.run_mary
```

The root `run_mary.py` is only a compatibility shim. It does not create a second
Mary implementation.
