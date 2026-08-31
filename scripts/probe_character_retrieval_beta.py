from pathlib import Path
import sys

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))

from mary.character import CharacterSourcebook

book = CharacterSourcebook.from_environment()
queries = [
    "someone steals food from Mary",
    "Mary is genuinely angry",
    "Mary comforts someone she loves",
    "does AI Mary remember growing up with Dave",
    "Mary keeps saying bucko",
    "Mary likes someone and gets flustered",
]

print("records:", book.snapshot()["records"])
print("errors:", book.snapshot()["errors"])
print("hash:", book.snapshot()["sourcebook_hash"])

for q in queries:
    s = book.select(q, limit=6, max_characters=4200)
    print("\nQUERY:", q)
    print("selected:", len(s.records))
    for r in s.records:
        print(r.labels, r.heading, "=>", r.text[:200])
