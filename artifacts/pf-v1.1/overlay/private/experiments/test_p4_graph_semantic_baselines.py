from __future__ import annotations

import numpy as np

from private.experiments.run_p4_graph_semantic_baselines import (
    _calibration_metrics,
    _canonical_action,
    _contains_forbidden_key,
    _fit_platt,
    _pair_graph,
    _rank,
)


def test_canonical_action_is_unicode_and_whitespace_stable() -> None:
    assert _canonical_action("  CLICK(\uff33ubmit)\n") == "click(submit)"


def test_pair_graph_merges_near_identical_actions_but_preserves_detours() -> None:
    same = _pair_graph(
        ["click(text='Submit')", "type(text='owl')"],
        ["CLICK(text='Submit')", "type(text='owl')"],
    )
    detour = _pair_graph(
        ["click(text='Submit')", "type(text='owl')"],
        ["click(text='Help')", "click(text='Back')", "type(text='owl')"],
    )
    assert same.prediction == "equivalent"
    assert same.node_jaccard == 1.0
    assert same.edge_jaccard == 1.0
    assert detour.composite_similarity < same.composite_similarity


def test_platt_calibration_separates_ordered_toy_scores() -> None:
    scores = np.asarray([-1.0, -0.5, -0.2, 0.2, 0.5, 1.0])
    labels = np.asarray([0.0, 0.0, 0.0, 1.0, 1.0, 1.0])
    intercept, slope, iterations = _fit_platt(scores, labels)
    metrics = _calibration_metrics(scores, labels, intercept, slope)
    assert slope > 0
    assert 0 < iterations <= 100
    assert metrics["accuracy"] == 1.0
    assert metrics["brier"] < 0.1


def test_rank_averages_ties() -> None:
    assert _rank(np.asarray([2.0, 1.0, 2.0])).tolist() == [2.5, 1.0, 2.5]


def test_forbidden_content_key_scan_is_recursive() -> None:
    assert _contains_forbidden_key({"nested": [{"goal": "hidden"}]})
    assert not _contains_forbidden_key({"taskId": "safe", "digest": "sha256:00"})
