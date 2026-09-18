from __future__ import annotations

from pathlib import Path

from mary.knowledge import (
    KnowledgeEvaluationCase,
    KnowledgeFabric,
    KnowledgeFabricEvaluator,
)


def _fabric(tmp_path: Path) -> KnowledgeFabric:
    alpha = tmp_path / "alpha"
    beta = tmp_path / "beta"
    alpha.mkdir()
    beta.mkdir()
    (alpha / "restricted.md").write_text(
        "orionneedle is the alpha-only phrase.",
        encoding="utf-8",
    )
    (beta / "manual.md").write_text(
        "nebularouter is the verified beta manual procedure. "
        + "reference " * 700,
        encoding="utf-8",
    )
    fabric = KnowledgeFabric(
        tmp_path / "knowledge" / "registry.json",
        index_path=tmp_path / "knowledge" / "index.sqlite3",
    )
    fabric.register(
        pack_id="alpha",
        title="Alpha",
        collection="project-a",
        kind="local_files",
        location=str(alpha),
        query_mode="fts",
    )
    fabric.register(
        pack_id="beta",
        title="Beta",
        collection="manuals",
        kind="local_files",
        location=str(beta),
        query_mode="fts",
    )
    fabric.index_local_pack("alpha")
    fabric.index_local_pack("beta")
    return fabric


def test_evaluator_checks_recall_citations_scope_and_budget(tmp_path: Path):
    result = KnowledgeFabricEvaluator(_fabric(tmp_path)).evaluate_case(
        KnowledgeEvaluationCase(
            case_id="beta-manual",
            query="nebularouter",
            pack_ids=("beta",),
            expected_pack_ids=("beta",),
            expected_locators=("manual.md",),
            excluded_locators=("restricted.md",),
            require_expected_in_context=True,
            context_budget_characters=2000,
            limit=12,
        )
    )
    assert result.passed is True
    assert result.citation_coverage == 1.0
    assert result.model_context_characters <= result.context_budget_characters
    assert result.seen_pack_ids == ("beta",)
    assert "manual.md" in result.seen_locators
    assert "manual.md" in result.selected_locators


def test_evaluator_detects_excluded_and_disabled_source_stays_absent(tmp_path: Path):
    fabric = _fabric(tmp_path)
    evaluator = KnowledgeFabricEvaluator(fabric)
    before = evaluator.evaluate_case(
        KnowledgeEvaluationCase(
            case_id="before",
            query="orionneedle",
            excluded_locators=("restricted.md",),
            minimum_hits=0,
        )
    )
    assert before.passed is False
    assert any("excluded locator" in item for item in before.failures)

    fabric.disable_document("alpha", "restricted.md")
    after = evaluator.evaluate_case(
        KnowledgeEvaluationCase(
            case_id="after",
            query="orionneedle",
            excluded_locators=("restricted.md",),
            minimum_hits=0,
        )
    )
    assert after.passed is True
    assert after.raw_hits == 0


def test_evaluator_summary_is_non_promoting(tmp_path: Path):
    summary = KnowledgeFabricEvaluator(_fabric(tmp_path)).evaluate(
        [
            KnowledgeEvaluationCase(
                case_id="manual",
                query="nebularouter",
                expected_pack_ids=("beta",),
                expected_locators=("manual.md",),
            ),
            KnowledgeEvaluationCase(
                case_id="off",
                query="anything",
                retrieval_mode="off",
                minimum_hits=0,
                require_citations=False,
            ),
        ]
    )
    assert summary["all_passed"] is True
    assert summary["passed"] == 2
    assert "no LLM judge" in summary["policy"]
    assert "automatic" in summary["policy"]
