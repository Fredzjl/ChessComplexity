"""Local Stockfish adapter for root-position engine annotations."""

from __future__ import annotations

import shutil
from dataclasses import dataclass, field
from pathlib import Path

import chess
import chess.engine


def resolve_stockfish_binary(explicit_path: str | Path | None = None) -> str:
    """Resolve the Stockfish binary from an explicit path or the local PATH."""
    if explicit_path:
        path = Path(explicit_path)
        if path.exists():
            return str(path)
        raise FileNotFoundError(f"Stockfish binary not found at {explicit_path}")

    for candidate in ["stockfish", "/opt/homebrew/bin/stockfish", "/usr/local/bin/stockfish"]:
        resolved = shutil.which(candidate) if "/" not in candidate else candidate
        if resolved and Path(resolved).exists():
            return str(resolved)

    raise FileNotFoundError("Unable to find a local Stockfish binary")


def score_payload(score: chess.engine.PovScore, turn: chess.Color) -> dict[str, object]:
    """Convert a python-chess score object into serializable payload fields."""
    pov_score = score.pov(turn)
    mate = pov_score.mate()
    cp = pov_score.score()
    if mate is not None:
        score_text = f"M{mate:+d}"
    elif cp is not None:
        score_text = f"{cp / 100:+.2f}"
    else:
        score_text = "n/a"

    return {
        "cp": cp,
        "mate": mate,
        "score_text": score_text,
        "score_sort_value": sortable_score_value(cp=cp, mate=mate),
    }


def san_line(board: chess.Board, pv: list[chess.Move], *, max_plies: int = 6) -> str:
    """Convert a PV line into a readable SAN sequence."""
    if not pv:
        return ""
    return board.variation_san(pv[:max_plies])


def sortable_score_value(*, cp: int | None, mate: int | None) -> int:
    """Map cp and mate scores onto one signed axis for robust comparisons."""
    if cp is not None:
        return int(cp)
    if mate is None:
        return 0
    sign = 1 if mate > 0 else -1
    return sign * (100_000 - min(abs(int(mate)), 99_999))


@dataclass(slots=True)
class StockfishAdapter:
    """Local interface for root-position Stockfish analysis."""

    binary_path: str | Path | None = None
    threads: int = 4
    hash_mb: int = 128
    movetime_ms: int = 120
    multipv: int = 5
    engine: chess.engine.SimpleEngine | None = field(default=None, init=False)

    def load(self) -> None:
        """Launch the local Stockfish process and configure basic options."""
        if self.engine is not None:
            return

        resolved_binary = resolve_stockfish_binary(self.binary_path)
        self.engine = chess.engine.SimpleEngine.popen_uci(resolved_binary)
        self.engine.configure(
            {
                "Threads": self.threads,
                "Hash": self.hash_mb,
            }
        )

    def close(self) -> None:
        """Close the local engine process."""
        if self.engine is not None:
            self.engine.quit()
            self.engine = None

    def analyse(self, fen: str) -> dict[str, object]:
        """Analyse one FEN and return top engine moves with shallow PVs."""
        board = chess.Board(fen)
        return self.analyse_board(board)

    def analyse_board(
        self,
        board: chess.Board,
        *,
        pov_color: chess.Color | None = None,
    ) -> dict[str, object]:
        """Analyse one board and score every move from one consistent POV."""
        if self.engine is None:
            self.load()

        score_pov = board.turn if pov_color is None else pov_color
        info_list = self.engine.analyse(
            board,
            chess.engine.Limit(time=self.movetime_ms / 1000),
            multipv=self.multipv,
        )
        if isinstance(info_list, dict):
            info_list = [info_list]
        else:
            info_list = sorted(
                info_list,
                key=lambda info: int(info.get("multipv", self.multipv + 1)),
            )

        moves: list[dict[str, object]] = []
        for rank, info in enumerate(info_list, start=1):
            pv = info.get("pv", [])
            if not pv:
                continue
            first_move = pv[0]
            first_move_san = board.san(first_move)
            score_info = score_payload(info["score"], score_pov)
            moves.append(
                {
                    "rank": rank,
                    "multipv": int(info.get("multipv", rank)),
                    "uci": first_move.uci(),
                    "san": first_move_san,
                    "depth": info.get("depth"),
                    "seldepth": info.get("seldepth"),
                    "nodes": info.get("nodes"),
                    "score_cp": score_info["cp"],
                    "score_mate": score_info["mate"],
                    "score_text": score_info["score_text"],
                    "score_sort_value": score_info["score_sort_value"],
                    "pv_uci": [move.uci() for move in pv[:6]],
                    "pv_san": san_line(board, pv, max_plies=6),
                }
            )

        return {
            "fen": board.fen(),
            "engine_name": "stockfish",
            "binary_path": resolve_stockfish_binary(self.binary_path),
            "movetime_ms": self.movetime_ms,
            "multipv": self.multipv,
            "moves": moves,
        }
