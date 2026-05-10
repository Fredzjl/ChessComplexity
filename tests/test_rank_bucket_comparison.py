"""Tests for experiment-2 rank bucket helpers."""

from src.analysis.rank_bucket_comparison import elo_bucket_label, elo_bucket_start


def test_elo_bucket_start_rounds_down_to_bucket_width() -> None:
    assert elo_bucket_start(1341, 100) == 1300


def test_elo_bucket_label_formats_closed_range() -> None:
    assert elo_bucket_label(1300, 100) == "1300-1399"
