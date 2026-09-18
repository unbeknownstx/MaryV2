from __future__ import annotations

from pathlib import Path

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
