from __future__ import annotations

from pathlib import Path
import zipfile

import pytest

from mary.knowledge import KnowledgeFabric


def test_knowledge_fabric_is_lazy_until_a_real_pack_is_registered(tmp_path: Path):
    registry = tmp_path / "knowledge" / "fabric.json"
    index = tmp_path / "knowledge" / "fabric.sqlite3"
    fabric = KnowledgeFabric(registry, index_path=index)

    assert registry.exists() is False
    assert index.exists() is False
    assert fabric.status()["packs"] == 0
    assert registry.exists() is False
    assert index.exists() is False


def test_local_document_pack_builds_rebuildable_fts_evidence(tmp_path: Path):
    docs = tmp_path / "docs"
    docs.mkdir()
    (docs / "networking.md").write_text(
        "# VLAN notes\nA VLAN separates broadcast domains on a switched network.",
        encoding="utf-8",
    )
    (docs / ".env").write_text("SECRET=do-not-index", encoding="utf-8")

    fabric = KnowledgeFabric(
        tmp_path / "knowledge" / "fabric.json",
        index_path=tmp_path / "knowledge" / "fabric.sqlite3",
    )
    pack = fabric.register(
        pack_id="ccna",
        title="CCNA local notes",
        kind="local_files",
        location=str(docs),
        query_mode="fts",
        topics=("networking", "ccna", "vlans"),
        license="creator-owned",
    )
    result = fabric.index_local_pack(pack.id)

    assert result["indexed"] == 1
    assert result["content_fingerprint"]
    hits = fabric.search("broadcast domains", pack_ids=(pack.id,), limit=5)
    assert hits
    assert hits[0].pack_id == pack.id
    assert hits[0].collection == "default"
    assert hits[0].citation_id.startswith("knowledge:ccna:")
    assert hits[0].source_date
    assert hits[0].indexed_at
    assert "VLAN" in hits[0].title or "broadcast" in hits[0].snippet
    assert "do-not-index" not in " ".join(item.snippet for item in hits)

    status = fabric.status()
    assert status["indexed_documents"] == 1
    assert status["authority"].startswith("retrieved evidence")


def test_kiwix_pack_requires_local_or_private_endpoint(tmp_path: Path):
    fabric = KnowledgeFabric(tmp_path / "fabric.json")

    with pytest.raises(ValueError, match="local/private"):
        fabric.register(
            title="unsafe",
            kind="kiwix",
            location="https://example.com",
            query_mode="direct",
        )

    pack = fabric.register(
        pack_id="offline-wiki",
        title="Offline Wikipedia",
        kind="kiwix",
        location="http://127.0.0.1:8080",
        query_mode="direct",
        topics=("wikipedia", "reference"),
        license="content-specific",
    )
    assert pack.local_only is True
    assert fabric.plan("wikipedia history")[0]["pack_id"] == "offline-wiki"


def test_recommended_pack_candidates_are_disabled_metadata_only(tmp_path: Path):
    fabric = KnowledgeFabric(tmp_path / "fabric.json")
    rows = fabric.seed_recommended_candidates()

    assert {item.id for item in rows} == {
        "candidate_kiwix",
        "candidate_qdrant_edge",
        "candidate_local_docs",
    }
    assert all(item.enabled is False for item in rows)
    assert fabric.search("anything") == []


def test_large_documents_are_chunked_and_docx_is_local_extractable(tmp_path: Path):
    docs = tmp_path / "docs"
    docs.mkdir()
    docx = docs / "book.docx"
    paragraphs = "".join(
        f"<w:p><w:r><w:t>Mary knowledge paragraph {index} " +
        ("network topology evidence " * 40) +
        "</w:t></w:r></w:p>"
        for index in range(40)
    )
    document_xml = (
        '<?xml version="1.0" encoding="UTF-8" standalone="yes"?>'
        '<w:document xmlns:w="http://schemas.openxmlformats.org/wordprocessingml/2006/main">'
        f"<w:body>{paragraphs}</w:body></w:document>"
    )
    with zipfile.ZipFile(docx, "w") as archive:
        archive.writestr("word/document.xml", document_xml)

    fabric = KnowledgeFabric(
        tmp_path / "knowledge" / "fabric.json",
        index_path=tmp_path / "knowledge" / "fabric.sqlite3",
    )
    pack = fabric.register(
        pack_id="book",
        title="Local Book",
        kind="local_files",
        location=str(docs),
        query_mode="fts",
        topics=("network", "book"),
    )
    result = fabric.index_local_pack(pack.id)

    assert result["files_seen"] == 1
    assert result["chunks_indexed"] > 1
    hits = fabric.search("network topology evidence", pack_ids=(pack.id,), limit=5)
    assert hits
    assert all(item.locator.startswith("book.docx") for item in hits)


def test_chunker_bounds_large_corpus_segments_without_changing_source_authority():
    body = "\n\n".join(
        f"Section {index}. " + ("bounded retrieval text " * 100)
        for index in range(20)
    )
    chunks = KnowledgeFabric._document_chunks(
        body,
        target_characters=1800,
        overlap_characters=200,
    )
    assert len(chunks) > 1
    assert all(len(chunk) <= 2000 for chunk in chunks)
    assert any("Section 0" in chunk for chunk in chunks)



def test_document_activation_survives_index_as_durable_pack_policy(tmp_path: Path):
    docs = tmp_path / "docs-activation"
    docs.mkdir()
    (docs / "alpha.md").write_text(
        "Alpha source contains the singular quasarneedle fact.",
        encoding="utf-8",
    )
    (docs / "beta.md").write_text(
        "Beta source contains ordinary reference text.",
        encoding="utf-8",
    )
    fabric = KnowledgeFabric(
        tmp_path / "knowledge" / "activation.json",
        index_path=tmp_path / "knowledge" / "activation.sqlite3",
    )
    pack = fabric.register(
        pack_id="activation",
        title="Activation corpus",
        kind="local_files",
        location=str(docs),
        query_mode="fts",
        collection="project-reference",
    )
    fabric.index_local_pack(pack.id)

    assert fabric.search("quasarneedle", pack_ids=(pack.id,))
    disabled = fabric.disable_document(pack.id, "alpha.md")
    assert disabled["enabled"] is False
    assert "alpha.md" in fabric.get(pack.id).disabled_documents
    assert fabric.search("quasarneedle", pack_ids=(pack.id,)) == []

    # Rebuilding the disposable FTS index must not erase creator activation policy.
    fabric.index_local_pack(pack.id)
    assert fabric.search("quasarneedle", pack_ids=(pack.id,)) == []
    enabled = fabric.enable_document(pack.id, "alpha.md")
    assert enabled["enabled"] is True
    assert fabric.search("quasarneedle", pack_ids=(pack.id,))


def test_collection_switch_and_request_level_retrieval_mode(tmp_path: Path):
    docs = tmp_path / "docs-collection"
    docs.mkdir()
    (docs / "manual.md").write_text(
        "The nebularouter procedure is documented here.",
        encoding="utf-8",
    )
    fabric = KnowledgeFabric(
        tmp_path / "knowledge" / "collection.json",
        index_path=tmp_path / "knowledge" / "collection.sqlite3",
    )
    pack = fabric.register(
        pack_id="manuals",
        title="Manuals",
        kind="local_files",
        location=str(docs),
        query_mode="fts",
        collection="manuals",
    )
    fabric.index_local_pack(pack.id)

    assert fabric.search("nebularouter", retrieval_mode="off") == []
    assert fabric.search("nebularouter", retrieval_mode="lexical")
    changed = fabric.disable_collection("MANUALS")
    assert changed[0].enabled is False
    assert fabric.search("nebularouter") == []
    fabric.enable_collection("manuals")
    assert fabric.search("nebularouter")

    status = fabric.status()
    assert status["collections"]["manuals"]["packs"] == 1
    assert "off" in status["retrieval_modes"]


def test_local_corpus_refresh_plan_is_change_aware_and_policy_scoped(tmp_path: Path):
    docs = tmp_path / "corpus"
    docs.mkdir()
    (docs / "public.md").write_text("version one reference", encoding="utf-8")
    (docs / "private.md").write_text("must stay excluded", encoding="utf-8")
    (docs / "notes.txt").write_text("not in include pattern", encoding="utf-8")

    fabric = KnowledgeFabric(
        tmp_path / "knowledge" / "refresh.json",
        index_path=tmp_path / "knowledge" / "refresh.sqlite3",
    )
    pack = fabric.register(
        pack_id="curated",
        title="Curated corpus",
        kind="local_files",
        location=str(docs),
        query_mode="fts",
        ingest_policy="on_change",
        metadata={
            "include_patterns": ["*.md"],
            "exclude_patterns": ["private*"],
        },
    )

    before = fabric.local_refresh_plan(pack.id)
    assert before["ingest_policy"] == "on_change"
    assert before["added"] == ["public.md"]
    assert before["automatic_mutation_performed"] is False

    indexed = fabric.index_local_pack(pack.id)
    assert indexed["files_seen"] == 1
    assert [row["locator"] for row in fabric.documents(pack.id)] == ["public.md"]
    assert fabric.local_refresh_plan(pack.id)["has_changes"] is False

    (docs / "public.md").write_text("version two reference", encoding="utf-8")
    (docs / "new.md").write_text("new source", encoding="utf-8")
    changed = fabric.local_refresh_plan(pack.id)
    assert changed["changed"] == ["public.md"]
    assert changed["added"] == ["new.md"]
    assert changed["recommended_action"] == "explicit_index"

    fabric.index_local_pack(pack.id)
    assert fabric.local_refresh_plan(pack.id)["has_changes"] is False
    assert fabric.status()["ingest_policies"]["on_change"] == 1


def test_legacy_pack_without_ingest_policy_decodes_as_manual(tmp_path: Path):
    registry = tmp_path / "legacy.json"
    registry.write_text(
        '{"version":2,"packs":[{"id":"legacy","title":"Legacy","collection":"default",'
        '"kind":"custom","query_mode":"catalog_only","location":"legacy","enabled":false,'
        '"local_only":true,"topics":[],"license":"unknown","trust":"candidate",'
        '"source":"test","content_fingerprint":"","created_at":"","updated_at":"",'
        '"disabled_documents":[],"metadata":{}}]}',
        encoding="utf-8",
    )
    pack = KnowledgeFabric(registry).get("legacy")
    assert pack.ingest_policy == "manual"
