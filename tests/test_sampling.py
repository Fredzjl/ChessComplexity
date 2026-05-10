"""Tests for reproducible sampling helpers."""

from src.data.sampling import game_sample_from_pgn, sample_elo_summary, spread_select


def make_game(game_id: str, white_elo: int, black_elo: int) -> str:
    return f"""[Event "Rated Blitz game"]
[Site "https://lichess.org/{game_id}"]
[White "W{game_id}"]
[Black "B{game_id}"]
[Result "1-0"]
[WhiteElo "{white_elo}"]
[BlackElo "{black_elo}"]
[TimeControl "300+0"]

1. e4 e5 2. Nf3 Nc6
"""


def test_game_sample_from_pgn_extracts_average_elo() -> None:
    sample = game_sample_from_pgn(make_game("g1", 1600, 1800))
    assert sample is not None
    assert sample.game_id == "g1"
    assert sample.average_elo == 1700


def test_spread_select_covers_range() -> None:
    samples = [
        game_sample_from_pgn(make_game(f"g{index}", 1200 + index * 50, 1250 + index * 50))
        for index in range(10)
    ]
    chosen = spread_select([sample for sample in samples if sample is not None], 4)
    chosen_elo = [sample.average_elo for sample in chosen]
    assert chosen_elo[0] == 1225
    assert chosen_elo[-1] == 1675
    assert len({sample.game_id for sample in chosen}) == 4


def test_sample_elo_summary_counts_buckets() -> None:
    samples = [
        game_sample_from_pgn(make_game("a", 1500, 1500)),
        game_sample_from_pgn(make_game("b", 1700, 1700)),
        game_sample_from_pgn(make_game("c", 1900, 1900)),
    ]
    summary = sample_elo_summary([sample for sample in samples if sample is not None], bucket_count=3)
    assert summary["count_with_average_elo"] == 3
    assert len(summary["buckets"]) == 3
