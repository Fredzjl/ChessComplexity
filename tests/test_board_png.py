"""Tests for board PNG rendering."""

from pathlib import Path

import chess

from src.rendering.board_png import render_position_png


def test_render_position_png_creates_nonempty_file(tmp_path: Path) -> None:
    board = chess.Board()
    output_path = tmp_path / "start_position.png"

    render_position_png(
        board,
        output_path,
        position_id="startpos",
        title="Start Position",
        subtitle="Smoke test render",
    )

    assert output_path.exists()
    assert output_path.stat().st_size > 0
