"""Print retrieval results for the six Character Authority probes."""
from __future__ import annotations

from pathlib import Path
import sys

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))

from mary.character import CharacterSourcebook

book = CharacterSourcebook.from_environment()
snapshot = book.snapshot()

print("=== SOURCEBOOK ===")
print("enabled:", snapshot.get("enabled"))
print("records:", snapshot.get("records"))
print("sources:", snapshot.get("sources"))
print("errors:", snapshot.get("errors"))
print("hash:", snapshot.get("sourcebook_hash"))

queries = [
    "someone steals food from Mary",
    "Mary is genuinely angry",
    "Mary comforts someone she loves",
    "does AI Mary remember growing up with Dave",
    "Mary keeps saying bucko",
    "Mary likes someone and gets flustered",
]

for query in queries:
    selection = book.select(query, limit=6, max_characters=4200)
    print("\nQUERY:", query)
    print("selected:", len(selection.records))
    for record in selection.records:
        print(
            record.labels,
            record.heading,
            "=>",
            record.text[:220],
        )
