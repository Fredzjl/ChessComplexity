"""Tests for PGN parsing and middlegame filtering."""

from pathlib import Path

from src.data import apply_middlegame_filter, parse_games


SAMPLE_PGN = """[Event "Rated Blitz game"]
[Site "https://lichess.org/testgame1"]
[UTCDate "2026.05.09"]
[UTCTime "12:00:00"]
[White "Alice"]
[Black "Bob"]
[Result "1-0"]
[WhiteElo "1800"]
[BlackElo "1750"]
[TimeControl "300+0"]

1. e4 e5 2. Nf3 Nc6 3. Bb5 a6 4. Ba4 Nf6
"""


def test_parse_games_builds_stable_position_ids(tmp_path: Path) -> None:
    pgn_path = tmp_path / "sample.pgn"
    pgn_path.write_text(SAMPLE_PGN, encoding="utf-8")

    games, positions = parse_games(pgn_path)

    assert len(games) == 1
    assert len(positions) == 8
    assert positions[0]["position_id"] == "testgame1_ply_1"
    assert positions[-1]["position_id"] == "testgame1_ply_8"
    assert positions[0]["fullmove_number"] >= 1


def test_apply_middlegame_filter_marks_skip_reasons() -> None:
    records = [
        {
            "position_id": "g1_ply_1",
            "fullmove_number": 5,
            "remaining_white_pieces": 16,
            "remaining_black_pieces": 16,
        },
        {
            "position_id": "g1_ply_2",
            "fullmove_number": 12,
            "remaining_white_pieces": 7,
            "remaining_black_pieces": 16,
        },
        {
            "position_id": "g1_ply_3",
            "fullmove_number": 14,
            "remaining_white_pieces": 16,
            "remaining_black_pieces": 16,
        },
    ]

    annotated, eligible, summary = apply_middlegame_filter(
        records,
        min_fullmove=10,
        max_fullmove=30,
        min_remaining_pieces_per_side=8,
    )

    assert annotated[0]["skip_reasons"] == "before_min_fullmove"
    assert annotated[1]["skip_reasons"] == "white_below_piece_threshold"
    assert annotated[2]["eligible_middlegame"] is True
    assert len(eligible) == 1
    assert summary["eligible_middlegame"] == 1
