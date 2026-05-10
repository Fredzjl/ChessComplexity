"""Tests for small Stockfish adapter helpers."""

import chess
import chess.engine

from src.engines.stockfish_adapter import resolve_stockfish_binary, score_payload


def test_score_payload_formats_centipawn_score() -> None:
    payload = score_payload(chess.engine.PovScore(chess.engine.Cp(34), chess.WHITE), chess.WHITE)
    assert payload["cp"] == 34
    assert payload["mate"] is None
    assert payload["score_text"] == "+0.34"


def test_resolve_stockfish_binary_finds_local_install() -> None:
    assert resolve_stockfish_binary().endswith("stockfish")
