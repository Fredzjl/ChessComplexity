#!/usr/bin/env python3
"""Run Maia-2 3-ply policy expansion for every eligible middlegame position."""

from __future__ import annotations

import argparse
import csv
import json
import sys
from collections import deque
from datetime import datetime, timezone
from pathlib import Path

import chess
import yaml

REPO_ROOT = Path(__file__).resolve().parents[2]
if str(REPO_ROOT) not in sys.path:
    sys.path.insert(0, str(REPO_ROOT))

from src.engines.maia2_adapter import Maia2Adapter, qualifying_policy_items


def read_csv_rows(path: Path) -> list[dict[str, str]]:
    with path.open("r", encoding="utf-8", newline="") as handle:
        return list(csv.DictReader(handle))


def write_csv(path: Path, rows: list[dict[str, object]]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    if not rows:
        path.write_text("", encoding="utf-8")
        return

    fieldnames = list(rows[0].keys())
    with path.open("w", encoding="utf-8", newline="") as handle:
        writer = csv.DictWriter(handle, fieldnames=fieldnames)
        writer.writeheader()
        writer.writerows(rows)


def load_policy_config(config_path: Path) -> dict[str, object]:
    config = yaml.safe_load(config_path.read_text(encoding="utf-8"))
    return {
        "min_probability": float(config["complexity"]["min_move_probability"]),
        "expansion_plies": int(config["complexity"]["expansion_plies"]),
        "device": str(config["models"]["maia2"]["device"]),
    }


def safe_elo(raw_value: str | None, default: int = 1800) -> int:
    if not raw_value:
        return default
    try:
        return int(raw_value)
    except ValueError:
        return default


def node_id_for(position_id: str, path_uci: list[str]) -> str:
    if not path_uci:
        return f"{position_id}__root"
    return f"{position_id}__{'__'.join(path_uci)}"


def node_elo_pair(board: chess.Board, root_row: dict[str, str]) -> tuple[int, int]:
    white_elo = safe_elo(root_row.get("white_elo"))
    black_elo = safe_elo(root_row.get("black_elo"))
    if board.turn == chess.WHITE:
        return white_elo, black_elo
    return black_elo, white_elo


def build_topk_rows(snapshot: dict[str, object], *, top_k: int) -> list[dict[str, object]]:
    rows: list[dict[str, object]] = []
    qualifying_moves = set(snapshot["qualifying_moves"])
    for rank, (move_uci, probability) in enumerate(list(snapshot["move_probs"].items())[:top_k], start=1):
        rows.append(
            {
                "root_position_id": snapshot["root_position_id"],
                "node_id": snapshot["node_id"],
                "parent_node_id": snapshot["parent_node_id"],
                "depth": snapshot["depth"],
                "path_uci": " ".join(snapshot["path_uci"]),
                "path_probability": snapshot["path_probability"],
                "rank": rank,
                "move_uci": move_uci,
                "probability": probability,
                "qualifies_for_expansion": move_uci in qualifying_moves,
                "fen": snapshot["fen"],
                "side_to_move": snapshot["side_to_move"],
                "win_prob": snapshot["win_prob"],
            }
        )
    return rows


def expand_root_position(
    root_row: dict[str, str],
    *,
    adapter: Maia2Adapter,
    min_probability: float,
    expansion_plies: int,
) -> tuple[list[dict[str, object]], list[dict[str, object]]]:
    snapshots: list[dict[str, object]] = []
    topk_rows: list[dict[str, object]] = []
    queue: deque[dict[str, object]] = deque(
        [
            {
                "position_id": root_row["position_id"],
                "parent_node_id": "",
                "path_uci": [],
                "path_probability": 1.0,
                "fen": root_row["fen"],
                "depth": 0,
            }
        ]
    )

    while queue:
        node = queue.popleft()
        board = chess.Board(str(node["fen"]))
        elo_self, elo_oppo = node_elo_pair(board, root_row)
        result = adapter.predict_policy(str(node["fen"]), elo_self=elo_self, elo_oppo=elo_oppo)
        qualifying = qualifying_policy_items(result["move_probs"], min_probability=min_probability)

        snapshot = {
            "timestamp_utc": datetime.now(timezone.utc).isoformat(),
            "root_position_id": root_row["position_id"],
            "root_game_id": root_row["game_id"],
            "node_id": node_id_for(root_row["position_id"], list(node["path_uci"])),
            "parent_node_id": str(node["parent_node_id"]),
            "depth": int(node["depth"]),
            "path_uci": list(node["path_uci"]),
            "path_probability": round(float(node["path_probability"]), 8),
            "fen": str(node["fen"]),
            "side_to_move": result["side_to_move"],
            "elo_self": elo_self,
            "elo_oppo": elo_oppo,
            "model_name": result["model_name"],
            "model_version": result["model_version"],
            "model_type": result["model_type"],
            "requested_device": result["requested_device"],
            "actual_device": result["actual_device"],
            "win_prob": result["win_prob"],
            "move_count": result["move_count"],
            "min_probability": min_probability,
            "qualifying_move_count": len(qualifying),
            "qualifying_moves": [move for move, _ in qualifying],
            "qualifying_probabilities": {move: prob for move, prob in qualifying},
            "move_probs": result["move_probs"],
        }
        snapshots.append(snapshot)
        topk_rows.extend(build_topk_rows(snapshot, top_k=20))

        if int(node["depth"]) >= expansion_plies - 1:
            continue

        for move_uci, probability in qualifying:
            child_board = chess.Board(str(node["fen"]))
            child_board.push(chess.Move.from_uci(move_uci))
            child_path = list(node["path_uci"]) + [move_uci]
            queue.append(
                {
                    "position_id": root_row["position_id"],
                    "parent_node_id": snapshot["node_id"],
                    "path_uci": child_path,
                    "path_probability": float(node["path_probability"]) * float(probability),
                    "fen": child_board.fen(),
                    "depth": int(node["depth"]) + 1,
                }
            )

    return snapshots, topk_rows


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument(
        "--positions-csv",
        default="outputs/runs/step_04_parse_filter/filtered/middlegame_positions.csv",
    )
    parser.add_argument("--config", default="configs/experiments/first_full_test.template.yaml")
    parser.add_argument("--output-dir", default="outputs/runs/step_06_policy_expansion")
    parser.add_argument("--model-type", default="rapid", choices=["rapid", "blitz"])
    parser.add_argument("--save-root", default="models/maia2")
    args = parser.parse_args()

    positions_csv = Path(args.positions_csv)
    config_path = Path(args.config)
    output_dir = Path(args.output_dir)
    policy_dir = output_dir / "policy"
    metadata_dir = output_dir / "metadata"
    policy_dir.mkdir(parents=True, exist_ok=True)
    metadata_dir.mkdir(parents=True, exist_ok=True)

    config = load_policy_config(config_path)
    adapter = Maia2Adapter(
        model_type=args.model_type,
        requested_device=str(config["device"]),
        save_root=args.save_root,
    )
    adapter.load()

    rows = read_csv_rows(positions_csv)
    raw_path = policy_dir / "raw_policy_snapshots.jsonl"
    topk_path = policy_dir / "topk_policy_snapshots.csv"
    failed_path = metadata_dir / "failed_inferences.csv"

    all_topk_rows: list[dict[str, object]] = []
    failed_rows: list[dict[str, object]] = []
    success_count = 0
    failure_count = 0
    queried_node_count = 0

    with raw_path.open("w", encoding="utf-8") as raw_handle:
        for index, root_row in enumerate(rows, start=1):
            try:
                snapshots, topk_rows = expand_root_position(
                    root_row,
                    adapter=adapter,
                    min_probability=float(config["min_probability"]),
                    expansion_plies=int(config["expansion_plies"]),
                )
                for snapshot in snapshots:
                    raw_handle.write(json.dumps(snapshot) + "\n")
                all_topk_rows.extend(topk_rows)
                queried_node_count += len(snapshots)
                success_count += 1
                if index % 25 == 0:
                    print(
                        json.dumps(
                            {
                                "progress_root_index": index,
                                "total_roots": len(rows),
                                "success_count": success_count,
                                "failure_count": failure_count,
                                "queried_node_count": queried_node_count,
                            }
                        )
                    )
            except Exception as exc:  # pragma: no cover - exercised on real runs
                failure_count += 1
                failed_rows.append(
                    {
                        "position_id": root_row["position_id"],
                        "game_id": root_row["game_id"],
                        "fen": root_row["fen"],
                        "error_type": type(exc).__name__,
                        "error_message": str(exc),
                    }
                )

    write_csv(topk_path, all_topk_rows)
    write_csv(failed_path, failed_rows)

    summary = {
        "timestamp_utc": datetime.now(timezone.utc).isoformat(),
        "positions_csv": str(positions_csv),
        "config_path": str(config_path),
        "model_type": args.model_type,
        "requested_device": str(config["device"]),
        "actual_device": adapter.actual_device,
        "eligible_root_positions": len(rows),
        "successful_root_positions": success_count,
        "failed_root_positions": failure_count,
        "queried_node_count": queried_node_count,
        "raw_snapshot_count": queried_node_count,
        "topk_row_count": len(all_topk_rows),
        "paths": {
            "raw_policy_snapshots_jsonl": str(raw_path),
            "topk_policy_snapshots_csv": str(topk_path),
            "failed_inferences_csv": str(failed_path),
        },
        "expansion": {
            "min_probability": config["min_probability"],
            "expansion_plies": config["expansion_plies"],
        },
    }
    (metadata_dir / "summary.json").write_text(json.dumps(summary, indent=2) + "\n", encoding="utf-8")
    print(json.dumps(summary, indent=2))


if __name__ == "__main__":
    main()
