#!/usr/bin/env python3
"""Render sample PNG boards from the local PGN dataset."""

from __future__ import annotations

import argparse
import json
import sys
from datetime import datetime, timezone
from pathlib import Path

import chess
import chess.pgn

REPO_ROOT = Path(__file__).resolve().parents[2]
if str(REPO_ROOT) not in sys.path:
    sys.path.insert(0, str(REPO_ROOT))

from src.rendering.board_png import render_position_png


def extract_board_at_fullmove(game: chess.pgn.Game, target_fullmove: int) -> tuple[chess.Board, str | None]:
    board = game.board()
    lastmove_uci: str | None = None
    for node in game.mainline():
        board.push(node.move)
        lastmove_uci = node.move.uci()
        if board.fullmove_number >= target_fullmove:
            break
    return board.copy(stack=False), lastmove_uci


def game_id_from_headers(game: chess.pgn.Game) -> str:
    site = game.headers.get("Site", "")
    return site.rsplit("/", 1)[-1] if "/" in site else "unknown_game"


def render_samples(
    pgn_path: Path,
    output_dir: Path,
    *,
    fullmove: int,
    max_games: int,
    board_size: int,
) -> list[dict[str, object]]:
    output_dir.mkdir(parents=True, exist_ok=True)
    records: list[dict[str, object]] = []

    with pgn_path.open("r", encoding="utf-8") as handle:
        for index in range(max_games):
            game = chess.pgn.read_game(handle)
            if game is None:
                break

            game_id = game_id_from_headers(game)
            white = game.headers.get("White", "White")
            black = game.headers.get("Black", "Black")
            result = game.headers.get("Result", "*")
            board, lastmove_uci = extract_board_at_fullmove(game, fullmove)
            position_id = f"{game_id}_fullmove_{fullmove}"
            output_path = output_dir / f"{position_id}.png"

            subtitle = f"{white} vs {black} | Result {result} | Last move {lastmove_uci or 'n/a'}"
            footer = (
                f"Game: {game_id} | Turn: {'White' if board.turn == chess.WHITE else 'Black'} | "
                f"Fullmove: {board.fullmove_number} | FEN: {board.fen()}"
            )
            render_position_png(
                board,
                output_path,
                position_id=position_id,
                title=f"Sample Position {index + 1}",
                subtitle=subtitle,
                footer=footer,
                lastmove_uci=lastmove_uci,
                board_size=board_size,
            )

            records.append(
                {
                    "position_id": position_id,
                    "game_id": game_id,
                    "white": white,
                    "black": black,
                    "result": result,
                    "fullmove": board.fullmove_number,
                    "turn": "white" if board.turn == chess.WHITE else "black",
                    "lastmove_uci": lastmove_uci,
                    "fen": board.fen(),
                    "image_path": str(output_path),
                }
            )

    return records


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--sample-pgn", default="data/raw/lichess_sample_10_games.pgn")
    parser.add_argument("--output-dir", default="outputs/reviews/manual_board_preview/images")
    parser.add_argument("--metadata-json", default="outputs/reviews/manual_board_preview/metadata/rendered_positions.json")
    parser.add_argument("--fullmove", type=int, default=20)
    parser.add_argument("--max-games", type=int, default=3)
    parser.add_argument("--board-size", type=int, default=720)
    args = parser.parse_args()

    pgn_path = Path(args.sample_pgn)
    output_dir = Path(args.output_dir)
    metadata_json = Path(args.metadata_json)
    metadata_json.parent.mkdir(parents=True, exist_ok=True)

    records = render_samples(
        pgn_path,
        output_dir,
        fullmove=args.fullmove,
        max_games=args.max_games,
        board_size=args.board_size,
    )

    payload = {
        "timestamp_utc": datetime.now(timezone.utc).isoformat(),
        "source_pgn": str(pgn_path),
        "fullmove": args.fullmove,
        "max_games": args.max_games,
        "rendered_count": len(records),
        "records": records,
    }
    metadata_json.write_text(json.dumps(payload, indent=2) + "\n", encoding="utf-8")
    print(json.dumps(payload, indent=2))


if __name__ == "__main__":
    main()
