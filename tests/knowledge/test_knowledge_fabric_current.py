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
    assert len(result["pipeline_fingerprint"]) == 64
    assert len(result["derivative_fingerprint"]) == 64
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
    assert len(indexed["pipeline_fingerprint"]) == 64
    assert len(indexed["derivative_fingerprint"]) == 64
    assert [row["locator"] for row in fabric.documents(pack.id)] == ["public.md"]
    current = fabric.local_refresh_plan(pack.id)
    assert current["pipeline_changed"] is False
    assert current["has_changes"] is False

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


def test_curation_report_detects_duplicates_and_drift_without_mutation(tmp_path: Path):
    docs_a = tmp_path / "a"
    docs_b = tmp_path / "b"
    docs_a.mkdir()
    docs_b.mkdir()
    shared = "same canonical reference body"
    (docs_a / "one.md").write_text(shared, encoding="utf-8")
    (docs_b / "copy.md").write_text(shared, encoding="utf-8")

    fabric = KnowledgeFabric(
        tmp_path / "knowledge" / "curation.json",
        index_path=tmp_path / "knowledge" / "curation.sqlite3",
    )
    a = fabric.register(
        pack_id="a",
        title="A",
        kind="local_files",
        location=str(docs_a),
        query_mode="fts",
    )
    b = fabric.register(
        pack_id="b",
        title="B",
        kind="local_files",
        location=str(docs_b),
        query_mode="fts",
    )
    fabric.index_local_pack(a.id)
    fabric.index_local_pack(b.id)

    clean = fabric.curation_report()
    assert clean["duplicate_content_group_count"] == 1
    assert clean["automatic_mutation_performed"] is False
    assert all(row["recommendations"] == ["none"] for row in clean["packs"])

    (docs_a / "one.md").write_text("changed reference body", encoding="utf-8")
    drift = fabric.curation_report("a")
    assert drift["packs"][0]["refresh"]["has_changes"] is True
    assert "explicit_refresh" in drift["packs"][0]["recommendations"]
    assert fabric.search("same canonical reference body", pack_ids=(a.id,))


def test_substrate_profile_maps_active_reference_and_derivative_tiers_without_scanning(tmp_path: Path):
    docs = tmp_path / "docs-profile"
    docs.mkdir()
    (docs / "manual.md").write_text("local substrate evidence", encoding="utf-8")

    fabric = KnowledgeFabric(
        tmp_path / "knowledge" / "profile.json",
        index_path=tmp_path / "knowledge" / "profile.sqlite3",
    )
    local = fabric.register(
        pack_id="local-docs",
        title="Local Docs",
        kind="local_files",
        location=str(docs),
        query_mode="fts",
        collection="projects",
    )
    fabric.index_local_pack(local.id)
    fabric.register(
        pack_id="offline-wiki",
        title="Offline Wiki",
        kind="kiwix",
        location="http://127.0.0.1:8080",
        query_mode="direct",
        collection="reference",
    )
    fabric.register(
        pack_id="vectors",
        title="Local Vectors",
        kind="qdrant",
        location="http://127.0.0.1:6333",
        query_mode="vector",
        collection="projects",
        metadata={
            "qdrant_collection": "mary_projects",
            "embedding_model": "test-embedding",
            "embedding_space_identity": "0123456789abcdef",
            "embedding_dimensions": 384,
        },
    )
    fabric.seed_recommended_candidates()

    profile = fabric.substrate_profile()

    assert profile["counts"]["active_local"] == 1
    assert profile["counts"]["offline_reference"] == 1
    assert profile["counts"]["semantic_derivative"] == 1
    assert profile["counts"]["catalog_candidates"] == 3
    assert profile["indexed_chunks"] == 1
    assert profile["enabled_retrieval_modes"] == ["direct", "fts", "vector"]
    assert profile["stale_derivatives"] == [
        {"pack_id": "vectors", "source_pack_id": "", "state": "unbuilt"}
    ]
    assert profile["stale_local_indexes"] == []
    assert profile["attention_required"] is True
    assert profile["automatic_scan_performed"] is False
    assert profile["automatic_rebuild_performed"] is False



def test_local_corpus_pipeline_change_requires_explicit_reindex(tmp_path: Path):
    import json

    docs = tmp_path / "pipeline-corpus"
    docs.mkdir()
    (docs / "manual.md").write_text(
        "Stable source text whose bytes do not change.",
        encoding="utf-8",
    )
    fabric = KnowledgeFabric(
        tmp_path / "knowledge" / "pipeline.json",
        index_path=tmp_path / "knowledge" / "pipeline.sqlite3",
    )
    pack = fabric.register(
        pack_id="pipeline",
        title="Pipeline corpus",
        kind="local_files",
        location=str(docs),
        query_mode="fts",
    )
    indexed = fabric.index_local_pack(pack.id)
    baseline = fabric.local_index_lineage(pack.id)
    assert baseline["state"] == "current"
    assert baseline["current"] is True
    assert baseline["derivative_fingerprint"] == indexed["derivative_fingerprint"]

    manifest_path = fabric._source_manifest_path(pack.id)
    manifest = json.loads(manifest_path.read_text(encoding="utf-8"))
    manifest["pipeline_fingerprint"] = "0" * 64
    manifest_path.write_text(json.dumps(manifest), encoding="utf-8")

    plan = fabric.local_refresh_plan(pack.id)
    assert plan["added"] == []
    assert plan["changed"] == []
    assert plan["removed"] == []
    assert plan["pipeline_changed"] is True
    assert plan["has_changes"] is True
    assert plan["recommended_action"] == "explicit_index"
    stale_lineage = fabric.local_index_lineage(pack.id)
    assert stale_lineage["state"] == "pipeline_stale"
    assert stale_lineage["current"] is False
    assert fabric.derivative_source_fingerprint(pack.id) == ""

    profile = fabric.substrate_profile()
    assert profile["stale_local_indexes"] == [
        {"pack_id": pack.id, "state": "pipeline_stale"}
    ]
    assert profile["attention_required"] is True

    report = fabric.curation_report(pack.id)
    assert report["packs"][0]["refresh"]["pipeline_changed"] is True
    assert "explicit_refresh" in report["packs"][0]["recommendations"]
    assert report["automatic_mutation_performed"] is False
