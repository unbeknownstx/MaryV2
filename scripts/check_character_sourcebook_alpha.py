"""Validate MaryV2 CharacterSourcebook against character_sources/active."""
from __future__ import annotations
from pathlib import Path
from mary.character import CharacterSourcebook

ROOT = Path(__file__).resolve().parents[1]
book = CharacterSourcebook.from_environment(root=ROOT)

snap = book.snapshot()
print("=== CHARACTER SOURCEBOOK ===")
print("enabled:", snap.get("enabled"))
print("records:", snap.get("records"))
print("sources:", snap.get("sources"))
print("source_names:", snap.get("source_names"))
print("kinds:", snap.get("kinds"))
print("labels:", snap.get("labels"))
print("errors:", snap.get("errors"))
print("hash:", snap.get("sourcebook_hash"))

queries = [
    "How would Mary react if someone stole food from her plate?",
    "What is Mary like when she is genuinely angry?",
    "How should Mary comfort someone she cares about?",
    "Does AI Mary remember growing up with Dave?",
    "Why shouldn't Mary say bucko all the time?",
    "How does Mary act around someone she genuinely likes?",
]
for query in queries:
    selection = book.select(query, limit=6, max_characters=4200)
    view = selection.prompt_view()
    print("\nQUERY:", query)
    for item in view.get("records", []):
        print("-", item.get("labels"), item.get("heading"), "=>", item.get("text","")[:240])
