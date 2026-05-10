#!/usr/bin/env python3
"""Aggregate policy-tree snapshots into provisional complexity scores."""

from __future__ import annotations

import argparse
import csv
import json
import statistics
import sys
from collections import defaultdict
from datetime import datetime, timezone
from pathlib import Path

import yaml

REPO_ROOT = Path(__file__).resolve().parents[2]
if str(REPO_ROOT) not in sys.path:
    sys.path.insert(0, str(REPO_ROOT))

from src.complexity.simple_metric import score_probability_tree


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


def load_complexity_config(config_path: Path) -> dict[str, object]:
    config = yaml.safe_load(config_path.read_text(encoding="utf-8"))
    return {
        "high_complexity_threshold": int(config["complexity"]["high_complexity_threshold"]),
        "min_probability": float(config["complexity"]["min_move_probability"]),
        "expansion_plies": int(config["complexity"]["expansion_plies"]),
    }


def load_snapshots_by_root(raw_jsonl_path: Path) -> dict[str, list[dict[str, object]]]:
    grouped: dict[str, list[dict[str, object]]] = defaultdict(list)
    with raw_jsonl_path.open("r", encoding="utf-8") as handle:
        for line in handle:
            snapshot = json.loads(line)
            grouped[str(snapshot["root_position_id"])].append(snapshot)
    return grouped


def failure_lookup(path: Path) -> dict[str, dict[str, str]]:
    rows = read_csv_rows(path)
    return {row["position_id"]: row for row in rows}


def quantiles_summary(values: list[int]) -> dict[str, float]:
    if not values:
        return {}
    ordered = sorted(values)
    if len(ordered) == 1:
        q25 = q50 = q75 = float(ordered[0])
    else:
        q25, q50, q75 = statistics.quantiles(ordered, n=4, method="inclusive")
    return {
        "min": min(ordered),
        "max": max(ordered),
        "mean": round(statistics.mean(ordered), 4),
        "median": statistics.median(ordered),
        "q25": q25,
        "q75": q75,
    }


def build_score_rows(
    position_rows: list[dict[str, str]],
    *,
    snapshots_by_root: dict[str, list[dict[str, object]]],
    failed_lookup: dict[str, dict[str, str]],
    threshold: int,
) -> tuple[list[dict[str, object]], list[dict[str, object]]]:
    score_rows: list[dict[str, object]] = []
    high_rows: list[dict[str, object]] = []

    for position in position_rows:
        position_id = position["position_id"]
        row: dict[str, object] = {
            "position_id": position_id,
            "game_id": position["game_id"],
            "ply_index": int(position["ply_index"]),
            "fullmove_number": int(position["fullmove_number"]),
            "side_to_move": position["side_to_move"],
            "fen": position["fen"],
            "white": position["white"],
            "black": position["black"],
            "white_elo": position["white_elo"],
            "black_elo": position["black_elo"],
            "remaining_white_pieces": int(position["remaining_white_pieces"]),
            "remaining_black_pieces": int(position["remaining_black_pieces"]),
            "image_path": position["image_path"],
            "high_complexity_threshold": threshold,
        }

        if position_id in snapshots_by_root:
            summary = score_probability_tree(snapshots_by_root[position_id])
            row.update(summary)
            row["inference_status"] = "success"
            row["failed_error_type"] = ""
            row["failed_error_message"] = ""
            row["high_complexity"] = summary["complexity_score"] >= threshold
            if row["high_complexity"]:
                high_rows.append(dict(row))
        else:
            failure = failed_lookup.get(position_id, {})
            row.update(
                {
                    "queried_node_count": 0,
                    "depth_0_qualifying_edges": "",
                    "depth_1_qualifying_edges": "",
                    "depth_2_qualifying_edges": "",
                    "complexity_score": "",
                    "inference_status": "failed_inference",
                    "failed_error_type": failure.get("error_type", ""),
                    "failed_error_message": failure.get("error_message", ""),
                    "high_complexity": "",
                }
            )
        score_rows.append(row)

    return score_rows, high_rows


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument(
        "--positions-csv",
        default="outputs/runs/step_04_parse_filter/filtered/middlegame_positions.csv",
    )
    parser.add_argument(
        "--raw-policy-jsonl",
        default="outputs/runs/step_06_policy_expansion/policy/raw_policy_snapshots.jsonl",
    )
    parser.add_argument(
        "--failed-inferences-csv",
        default="outputs/runs/step_06_policy_expansion/metadata/failed_inferences.csv",
    )
    parser.add_argument("--config", default="configs/experiments/first_full_test.template.yaml")
    parser.add_argument("--output-dir", default="outputs/runs/step_07_complexity_scoring")
    args = parser.parse_args()

    positions_csv = Path(args.positions_csv)
    raw_policy_jsonl = Path(args.raw_policy_jsonl)
    failed_inferences_csv = Path(args.failed_inferences_csv)
    config_path = Path(args.config)
    output_dir = Path(args.output_dir)
    complexity_dir = output_dir / "complexity"
    metadata_dir = output_dir / "metadata"

    config = load_complexity_config(config_path)
    position_rows = read_csv_rows(positions_csv)
    snapshots_by_root = load_snapshots_by_root(raw_policy_jsonl)
    failed_lookup = failure_lookup(failed_inferences_csv)
    score_rows, high_rows = build_score_rows(
        position_rows,
        snapshots_by_root=snapshots_by_root,
        failed_lookup=failed_lookup,
        threshold=int(config["high_complexity_threshold"]),
    )

    score_table_path = complexity_dir / "position_scores.csv"
    high_table_path = complexity_dir / "high_complexity_positions.csv"
    write_csv(score_table_path, score_rows)
    write_csv(high_table_path, high_rows)

    successful_scores = [int(row["complexity_score"]) for row in score_rows if row["complexity_score"] != ""]
    high_score_preview = sorted(
        [dict(row) for row in high_rows],
        key=lambda row: int(row["complexity_score"]),
        reverse=True,
    )[:10]

    summary = {
        "timestamp_utc": datetime.now(timezone.utc).isoformat(),
        "positions_csv": str(positions_csv),
        "raw_policy_jsonl": str(raw_policy_jsonl),
        "failed_inferences_csv": str(failed_inferences_csv),
        "config_path": str(config_path),
        "scored_positions": len(score_rows),
        "successful_scores": len(successful_scores),
        "failed_scores": len(score_rows) - len(successful_scores),
        "high_complexity_count": len(high_rows),
        "threshold": int(config["high_complexity_threshold"]),
        "expansion": {
            "min_probability": config["min_probability"],
            "expansion_plies": config["expansion_plies"],
        },
        "score_distribution": quantiles_summary(successful_scores),
        "top_high_complexity_preview": [
            {
                "position_id": row["position_id"],
                "complexity_score": int(row["complexity_score"]),
                "image_path": row["image_path"],
            }
            for row in high_score_preview
        ],
        "paths": {
            "position_scores_csv": str(score_table_path),
            "high_complexity_positions_csv": str(high_table_path),
        },
    }
    metadata_dir.mkdir(parents=True, exist_ok=True)
    (metadata_dir / "summary.json").write_text(json.dumps(summary, indent=2) + "\n", encoding="utf-8")
    print(json.dumps(summary, indent=2))


if __name__ == "__main__":
    main()
