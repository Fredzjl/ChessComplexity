"""Lichess PGN parsing helpers for the experiment pipeline."""

from __future__ import annotations

from pathlib import Path

import chess
import chess.pgn


def game_id_from_headers(game: chess.pgn.Game) -> str:
    """Return a stable Lichess game id from the PGN headers."""
    site = game.headers.get("Site", "")
    return site.rsplit("/", 1)[-1] if "/" in site else "unknown_game"


def count_pieces(board: chess.Board, color: chess.Color) -> int:
    """Count remaining pieces for one side, including the king."""
    return sum(1 for piece in board.piece_map().values() if piece.color == color)


def parse_games(pgn_path: str | Path) -> tuple[list[dict[str, object]], list[dict[str, object]]]:
    """Parse PGN games into game-level and position-level records."""
    pgn_path = Path(pgn_path)
    games: list[dict[str, object]] = []
    positions: list[dict[str, object]] = []

    with pgn_path.open("r", encoding="utf-8") as handle:
        game_index = 0
        while True:
            game = chess.pgn.read_game(handle)
            if game is None:
                break

            game_index += 1
            game_id = game_id_from_headers(game)
            headers = game.headers

            board = game.board()
            ply_index = 0
            for node in game.mainline():
                move = node.move
                san = board.san(move)
                board.push(move)
                ply_index += 1

                positions.append(
                    {
                        "position_id": f"{game_id}_ply_{ply_index}",
                        "game_id": game_id,
                        "game_index": game_index,
                        "ply_index": ply_index,
                        "fullmove_number": board.fullmove_number,
                        "side_to_move": "white" if board.turn == chess.WHITE else "black",
                        "fen": board.fen(),
                        "lastmove_uci": move.uci(),
                        "lastmove_san": san,
                        "remaining_white_pieces": count_pieces(board, chess.WHITE),
                        "remaining_black_pieces": count_pieces(board, chess.BLACK),
                        "white": headers.get("White", ""),
                        "black": headers.get("Black", ""),
                        "white_elo": headers.get("WhiteElo", ""),
                        "black_elo": headers.get("BlackElo", ""),
                        "result": headers.get("Result", ""),
                        "event": headers.get("Event", ""),
                        "time_control": headers.get("TimeControl", ""),
                    }
                )

            games.append(
                {
                    "game_index": game_index,
                    "game_id": game_id,
                    "site": headers.get("Site", ""),
                    "event": headers.get("Event", ""),
                    "utc_date": headers.get("UTCDate", ""),
                    "utc_time": headers.get("UTCTime", ""),
                    "white": headers.get("White", ""),
                    "black": headers.get("Black", ""),
                    "white_elo": headers.get("WhiteElo", ""),
                    "black_elo": headers.get("BlackElo", ""),
                    "result": headers.get("Result", ""),
                    "opening": headers.get("Opening", ""),
                    "eco": headers.get("ECO", ""),
                    "time_control": headers.get("TimeControl", ""),
                    "termination": headers.get("Termination", ""),
                    "ply_count": ply_index,
                    "final_fen": board.fen(),
                }
            )

    return games, positions
