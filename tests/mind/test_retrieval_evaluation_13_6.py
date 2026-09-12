from mary.mind.retrieval_evaluation import compare_rankings, evaluate_ranking


def test_metrics_are_deterministic_and_bounded():
    metrics = evaluate_ranking(["noise", "wanted", "other"], ["wanted"], k=3)
    assert metrics.hit_rate == 1.0
    assert 0.0 <= metrics.precision <= 1.0
    assert metrics.recall == 1.0
    assert metrics.reciprocal_rank == 0.5
    assert 0.0 <= metrics.ndcg <= 1.0


def test_comparison_detects_better_reranking():
    result = compare_rankings(
        ["noise-1", "noise-2", "wanted"],
        ["wanted", "noise-1", "noise-2"],
        ["wanted"],
        k=3,
    )
    assert result["improved"] is True
    assert result["delta"]["reciprocal_rank"] > 0
    assert result["delta"]["ndcg"] > 0
