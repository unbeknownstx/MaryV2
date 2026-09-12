from pathlib import Path


def test_relational_presence_docs_exist_and_reject_identity_fork():
    architecture = Path("docs/architecture/RELATIONAL_PRESENCE_13_8.md").read_text(encoding="utf-8")
    ui = Path("docs/architecture/RELATIONAL_PRESENCE_UI_13_8.md").read_text(encoding="utf-8")
    research = Path("docs/research/COMPANION_SYSTEMS_13_8.md").read_text(encoding="utf-8")
    assert "second relationship database" in architecture
    assert "same Mary" in ui
    assert "Romantic/partner behavior as relationship state" in research
