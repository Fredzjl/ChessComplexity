"""Helpers for rendering chess positions to PNG."""

from __future__ import annotations

import io
import textwrap
from pathlib import Path

import cairosvg
import chess
import chess.svg
from PIL import Image, ImageDraw, ImageFont

BOARD_COLORS = {
    "square light": "#f4e7c1",
    "square dark": "#bf8b4d",
    "margin": "#faf7f0",
    "coord": "#46352a",
}


def _coerce_board(board_or_fen: chess.Board | str) -> chess.Board:
    if isinstance(board_or_fen, chess.Board):
        return board_or_fen.copy(stack=False)
    return chess.Board(board_or_fen)


def _wrapped_lines(text: str, width: int) -> list[str]:
    if not text:
        return []
    return textwrap.wrap(text, width=width, break_long_words=False, break_on_hyphens=False)


def render_position_png(
    board_or_fen: chess.Board | str,
    output_path: str | Path,
    *,
    position_id: str | None = None,
    title: str | None = None,
    subtitle: str | None = None,
    footer: str | None = None,
    lastmove_uci: str | None = None,
    flipped: bool = False,
    coordinates: bool = True,
    board_size: int = 720,
) -> Path:
    """Render one position to a labeled PNG card and return the saved path."""

    board = _coerce_board(board_or_fen)
    output_path = Path(output_path)
    output_path.parent.mkdir(parents=True, exist_ok=True)

    lastmove = chess.Move.from_uci(lastmove_uci) if lastmove_uci else None
    svg = chess.svg.board(
        board=board,
        size=board_size,
        flipped=flipped,
        coordinates=coordinates,
        lastmove=lastmove,
        colors=BOARD_COLORS,
    )
    board_png_bytes = cairosvg.svg2png(bytestring=svg.encode("utf-8"))
    board_image = Image.open(io.BytesIO(board_png_bytes)).convert("RGBA")

    font = ImageFont.load_default()
    top_lines = []
    if title:
        top_lines.append(title)
    if subtitle:
        top_lines.extend(_wrapped_lines(subtitle, width=68))

    if footer is None:
        footer = (
            f"Turn: {'White' if board.turn == chess.WHITE else 'Black'} | "
            f"Fullmove: {board.fullmove_number} | FEN: {board.fen()}"
        )
    bottom_lines = _wrapped_lines(footer, width=82)

    line_height = 18
    top_padding = 18
    side_padding = 18
    gap = 14
    bottom_padding = 18
    top_block_height = (len(top_lines) * line_height) if top_lines else 0
    bottom_block_height = (len(bottom_lines) * line_height) if bottom_lines else 0

    canvas_width = board_image.width + side_padding * 2
    canvas_height = (
        top_padding
        + top_block_height
        + (gap if top_lines else 0)
        + board_image.height
        + (gap if bottom_lines else 0)
        + bottom_block_height
        + bottom_padding
    )

    canvas = Image.new("RGBA", (canvas_width, canvas_height), BOARD_COLORS["margin"])
    draw = ImageDraw.Draw(canvas)

    y = top_padding
    for line in top_lines:
        draw.text((side_padding, y), line, fill=BOARD_COLORS["coord"], font=font)
        y += line_height

    if top_lines:
        y += gap

    canvas.alpha_composite(board_image, (side_padding, y))
    y += board_image.height

    if bottom_lines:
        y += gap
        for line in bottom_lines:
            draw.text((side_padding, y), line, fill=BOARD_COLORS["coord"], font=font)
            y += line_height

    if position_id:
        draw.text(
            (canvas_width - side_padding - (len(position_id) * 6), top_padding),
            position_id,
            fill=BOARD_COLORS["coord"],
            font=font,
        )

    canvas.convert("RGB").save(output_path, format="PNG")
    return output_path
