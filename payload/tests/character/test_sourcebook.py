from pathlib import Path
from zipfile import ZipFile

from mary.character import CharacterSourcebook
from mary.core.mary import Mary
from mary.cognition.intent import Intent, IntentType


def test_sourcebook_selects_relevant_labeled_evidence(tmp_path: Path):
    path = tmp_path / "Mary_Corpus.md"
    path.write_text(
        "# Humor\n[DNA] Mary teases people she trusts, but does not turn every line into a joke.\n\n"
        "# Fiction\n[FC] Mary once crossed Union Station during a dangerous chase.\n\n"
        "# Anti-example\n[NEG] Mary should not sound like a customer-service script.\n",
        encoding="utf-8",
    )
    book = CharacterSourcebook.from_paths([path])
    selected = book.select("How should Mary tease someone she trusts?", limit=3)
    view = selected.prompt_view()

    assert book.snapshot()["records"] == 3
    assert view["records"]
    assert "teases people she trusts" in view["records"][0]["text"]
    assert view["records"][0]["boundary"] == "authored_character_evidence"


def test_docx_is_read_without_third_party_dependency(tmp_path: Path):
    path = tmp_path / "Mary_Definitive_Character_Bible.docx"
    xml = '''<?xml version="1.0" encoding="UTF-8" standalone="yes"?>
    <w:document xmlns:w="http://schemas.openxmlformats.org/wordprocessingml/2006/main"><w:body>
      <w:p><w:pPr><w:pStyle w:val="Heading1"/></w:pPr><w:r><w:t>Voice</w:t></w:r></w:p>
      <w:p><w:r><w:t>[DNA] Mary gets quieter, not sweeter, when she is genuinely hurt.</w:t></w:r></w:p>
    </w:body></w:document>'''
    with ZipFile(path, "w") as archive:
        archive.writestr("word/document.xml", xml)

    book = CharacterSourcebook.from_paths([path])
    assert book.snapshot()["records"] == 1
    result = book.select("How does Mary sound when hurt?").prompt_view()["records"][0]
    assert result["heading"] == "Voice"
    assert result["labels"] == ["DNA"]


def test_mary_turnmind_shares_the_same_sourcebook(monkeypatch, tmp_path: Path):
    source = tmp_path / "mary_corpus.md"
    source.write_text("[DNA] Mary values directness over ceremonial politeness.", encoding="utf-8")
    monkeypatch.setenv("MARY_CHARACTER_SOURCES", str(source))

    mary = Mary()
    assert mary.turn_mind.character_sourcebook is mary.character_sourcebook
    state = mary.turn_mind.build(
        input_text="Should you be direct with me?",
        intent=Intent(IntentType.QUESTION),
    )
    assert state.authored_character_context["records"]
    assert "directness" in state.authored_character_context["records"][0]["text"]
