"""Tests for Stockfish time-budget sweep helpers."""

from src.analysis.time_budget_sweep import common_prefix_length, jaccard_overlap


def test_jaccard_overlap_handles_partial_intersection() -> None:
    score = jaccard_overlap(["a", "b", "c"], ["b", "c", "d"])
    assert round(score, 4) == 0.5


def test_common_prefix_length_counts_until_first_difference() -> None:
    assert common_prefix_length(["a", "b", "c"], ["a", "b", "d"]) == 2
