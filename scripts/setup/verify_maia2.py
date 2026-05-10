#!/usr/bin/env python3
"""Verify local Maia-2 inference and save one example output."""

from __future__ import annotations

import argparse
import json
from datetime import datetime, timezone
from pathlib import Path

import chess
import chess.pgn
import torch
from maia2.inference import inference_each, prepare
from maia2.model import from_pretrained


def extract_test_fen(pgn_path: Path, target_fullmove: int = 20) -> tuple[str, str]:
    with pgn_path.open("r", encoding="utf-8") as handle:
        game = chess.pgn.read_game(handle)
    if game is None:
        raise RuntimeError(f"No game found in {pgn_path}")

    site = game.headers.get("Site", "")
    game_id = site.rsplit("/", 1)[-1] if "/" in site else "unknown_game"

    board = game.board()
    last_fen = board.fen()
    for node in game.mainline():
        board.push(node.move)
        last_fen = board.fen()
        if board.fullmove_number >= target_fullmove:
            break

    return last_fen, game_id


def maybe_move_to_mps(model: torch.nn.Module, requested_device: str) -> tuple[torch.nn.Module, str]:
    if requested_device != "mps":
        return model, "cpu"

    if not torch.backends.mps.is_available():
        return model, "cpu"

    model = model.to("mps")
    return model, "mps"


def file_info(path: Path) -> dict[str, object]:
    return {
        "path": str(path),
        "bytes": path.stat().st_size,
    }


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--model-type", default="rapid", choices=["rapid", "blitz"])
    parser.add_argument("--device", default="cpu", choices=["cpu", "mps"])
    parser.add_argument("--elo-self", type=int, default=1800)
    parser.add_argument("--elo-oppo", type=int, default=1800)
    parser.add_argument("--save-root", default="models/maia2")
    parser.add_argument("--sample-pgn", default="data/raw/lichess_sample_10_games.pgn")
    parser.add_argument(
        "--output-json",
        default="outputs/runs/step_03_maia2_verification/raw_model_output.json",
    )
    args = parser.parse_args()

    save_root = Path(args.save_root)
    output_json = Path(args.output_json)
    output_json.parent.mkdir(parents=True, exist_ok=True)
    save_root.mkdir(parents=True, exist_ok=True)

    fen, game_id = extract_test_fen(Path(args.sample_pgn))

    model = from_pretrained(args.model_type, "cpu", save_root=str(save_root))
    model, actual_device = maybe_move_to_mps(model, args.device)
    prepared = prepare()
    move_probs, win_prob = inference_each(model, prepared, fen, args.elo_self, args.elo_oppo)

    top_moves = list(move_probs.items())[:20]

    config_path = save_root / "config.yaml"
    checkpoint_path = save_root / f"{args.model_type}_model.pt"

    result = {
        "timestamp_utc": datetime.now(timezone.utc).isoformat(),
        "model_name": "maia2",
        "model_version": "0.9",
        "model_type": args.model_type,
        "requested_device": args.device,
        "actual_device": actual_device,
        "torch_version": torch.__version__,
        "torch_mps_available": torch.backends.mps.is_available(),
        "sample_game_id": game_id,
        "fen": fen,
        "elo_self": args.elo_self,
        "elo_oppo": args.elo_oppo,
        "win_prob": win_prob,
        "top_moves": top_moves,
        "move_count": len(move_probs),
        "checkpoint": file_info(checkpoint_path),
        "config": file_info(config_path),
    }
    output_json.write_text(json.dumps(result, indent=2) + "\n", encoding="utf-8")

    print(json.dumps(result, indent=2))


if __name__ == "__main__":
    main()
