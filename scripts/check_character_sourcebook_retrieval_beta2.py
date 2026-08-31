"""Verify the specific Dave-memory boundary fix."""
from pathlib import Path
import sys

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))

from mary.character import CharacterSourcebook

book = CharacterSourcebook.from_environment()
selection = book.select(
    "does AI Mary remember growing up with Dave",
    limit=6,
    max_characters=4200,
)

print("records:", book.snapshot()["records"])
print("selected:", len(selection.records))

for record in selection.records:
    print(record.labels, record.heading, "=>", record.text[:220])

headings = [record.heading for record in selection.records]

assert any(h.startswith("ID-003") for h in headings)
assert any("fake fictional autobiography" in h.lower() for h in headings)
assert any("AI relationship growth boundary" in h for h in headings)
assert any("Fictional relationship lens — Dave" in h for h in headings)
assert not any(h.startswith("HUM-002") for h in headings)

print("Beta2 Dave-memory boundary verification: PASS")
