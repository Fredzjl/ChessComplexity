"""Tests for the simple probability-tree complexity metric."""

from src.complexity.simple_metric import score_probability_tree


def test_score_probability_tree_sums_qualifying_edges_by_depth() -> None:
    snapshots = [
        {"depth": 0, "qualifying_move_count": 2},
        {"depth": 1, "qualifying_move_count": 3},
        {"depth": 1, "qualifying_move_count": 1},
        {"depth": 2, "qualifying_move_count": 4},
    ]

    summary = score_probability_tree(snapshots)

    assert summary["queried_node_count"] == 4
    assert summary["depth_0_qualifying_edges"] == 2
    assert summary["depth_1_qualifying_edges"] == 4
    assert summary["depth_2_qualifying_edges"] == 4
    assert summary["complexity_score"] == 10
