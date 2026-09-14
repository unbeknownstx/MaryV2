from mary.mind.retrieval_benchmark import (
    RetrievalCase,
    evaluate_case,
    evaluate_lane,
    promotion_decision,
    result_ids,
)


def _cases(count=8):
    return [
        RetrievalCase(f"case-{index}", (f"record-{index}",))
        for index in range(count)
    ]


def test_case_metrics_use_ranked_record_ids_only():
    case = RetrievalCase("favorite-color", ("semantic-42",))
    result = evaluate_case(case, ("noise", "semantic-42", "other"), k=3)
    assert result.hit_at_k is True
    assert result.first_relevant_rank == 2
    assert result.reciprocal_rank == 0.5
    assert result.precision_at_k == 1 / 3
    assert result.recall_at_k == 1.0
    assert "favorite" not in str(result.to_dict()).lower()


def test_strong_candidate_is_eligible_against_baseline():
    cases = _cases()
    baseline_rows = {
        case.case_id: (case.expected_record_ids[0], "noise")
        for case in cases
    }
    candidate_rows = dict(baseline_rows)
    baseline = evaluate_lane("lexical", cases, baseline_rows, k=2)
    candidate = evaluate_lane("vector", cases, candidate_rows, k=2)
    decision = promotion_decision(baseline, candidate)
    assert decision["promotion"] == "eligible"
    assert decision["reasons"] == []


def test_candidate_with_better_speed_but_bad_retrieval_quality_is_held():
    cases = _cases()
    baseline = evaluate_lane(
        "lexical",
        cases,
        {case.case_id: (case.expected_record_ids[0],) for case in cases},
        k=3,
    )
    candidate = evaluate_lane(
        "vector",
        cases,
        {case.case_id: ("wrong",) for case in cases},
        k=3,
    )
    decision = promotion_decision(baseline, candidate)
    assert decision["promotion"] == "hold"
    assert "hit_rate_below_floor" in decision["reasons"]
    assert "mrr_regressed_vs_baseline" in decision["reasons"]


def test_small_sample_never_auto_promotes():
    cases = _cases(2)
    baseline = evaluate_lane(
        "lexical", cases,
        {case.case_id: case.expected_record_ids for case in cases},
    )
    candidate = evaluate_lane(
        "hybrid", cases,
        {case.case_id: case.expected_record_ids for case in cases},
    )
    decision = promotion_decision(baseline, candidate)
    assert decision["promotion"] == "hold"
    assert "insufficient_cases" in decision["reasons"]


def test_missing_results_reduce_coverage():
    cases = _cases()
    rows = {
        case.case_id: case.expected_record_ids
        for case in cases[:4]
    }
    score = evaluate_lane("vector", cases, rows)
    assert score.coverage == 0.5


def test_result_ids_discards_content_and_scores():
    ids = result_ids([
        {"record_id": "a", "content": "private text", "score": 0.9},
        {"record_id": "b", "content": "other private text", "score": 0.8},
    ])
    assert ids == ("a", "b")
    assert "private" not in str(ids)
