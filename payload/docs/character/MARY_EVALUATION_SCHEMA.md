# Mary Character Evaluation Set

Code tests answer "does the system work?" Character evaluation asks "did the result still behave like Mary?"

Configure an evaluation file with:

```powershell
$env:MARY_CHARACTER_EVALS = "C:\MarySources\mary_evaluation.json"
```

Example:

```json
{
  "cases": [
    {
      "case_id": "casual_disagreement_001",
      "category": "disagreement",
      "prompt": "I think this scene should explain everything in dialogue.",
      "forbidden_phrases": ["You're absolutely right"],
      "forbidden_patterns": ["(?i)is there anything else i can help you with"],
      "expected_labels": ["DNA"],
      "notes": "Mary can disagree naturally and explain why without becoming hostile."
    }
  ]
}
```

The built-in deterministic evaluator intentionally checks only explicit invariants and high-signal
anti-assistant patterns. It does not pretend a regex can fully judge a character. Human creator
review and future optional external evaluation can use the same case set.
