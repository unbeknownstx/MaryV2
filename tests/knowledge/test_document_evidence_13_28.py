from __future__ import annotations

from mary.knowledge.document_evidence import DocumentEvidencePlanner


def test_new_document_is_refresh_then_unchanged(tmp_path) -> None:
    path = tmp_path / "notes.md"
    path.write_text("Mary project notes", encoding="utf-8")
    planner = DocumentEvidencePlanner()
    first = planner.plan([path])
    assert first[0].action == "refresh"
    manifest = planner.manifest(first)
    second = planner.plan([path], manifest)
    assert second[0].action == "unchanged"


def test_changed_document_refreshes(tmp_path) -> None:
    path = tmp_path / "notes.txt"
    path.write_text("one", encoding="utf-8")
    planner = DocumentEvidencePlanner()
    manifest = planner.manifest(planner.plan([path]))
    path.write_text("two", encoding="utf-8")
    result = planner.plan([path], manifest)
    assert result[0].action == "refresh"


def test_removed_approved_document_is_marked_for_derived_cleanup(tmp_path) -> None:
    path = tmp_path / "notes.md"
    path.write_text("hello", encoding="utf-8")
    planner = DocumentEvidencePlanner()
    manifest = planner.manifest(planner.plan([path]))
    result = planner.plan([], manifest)
    assert result[0].action == "remove"


def test_unsupported_document_does_not_enter_retrieval(tmp_path) -> None:
    path = tmp_path / "binary.exe"
    path.write_bytes(b"not a document")
    planner = DocumentEvidencePlanner()
    result = planner.plan([path])
    assert result[0].action == "skip"
    assert result[0].reason == "unsupported_type"


def test_records_are_derived_and_keep_creator_file_authority(tmp_path) -> None:
    path = tmp_path / "project.md"
    path.write_text("Alpha project fact.\n\nBeta project fact.", encoding="utf-8")
    planner = DocumentEvidencePlanner(max_chunk_characters=256)
    records = planner.records_for_file(path)
    assert records
    assert all(item.kind == "document_evidence" for item in records)
    assert all(item.authority == "creator_file_derived" for item in records)
    assert all(item.metadata["canonical_owner"] == "creator_file" for item in records)


def test_large_file_is_rejected_by_budget(tmp_path) -> None:
    path = tmp_path / "too-large.txt"
    path.write_text("x" * 4096, encoding="utf-8")
    planner = DocumentEvidencePlanner(max_file_bytes=1024)
    result = planner.plan([path])
    assert result[0].action == "skip"
    assert "budget" in result[0].reason
