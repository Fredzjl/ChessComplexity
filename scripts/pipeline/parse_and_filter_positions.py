#!/usr/bin/env python3
"""Parse PGN positions, filter middlegame candidates, and render PNG previews."""

from __future__ import annotations

import argparse
import csv
import json
import sys
from datetime import datetime, timezone
from pathlib import Path

import yaml

REPO_ROOT = Path(__file__).resolve().parents[2]
if str(REPO_ROOT) not in sys.path:
    sys.path.insert(0, str(REPO_ROOT))

from src.data import apply_middlegame_filter, parse_games
from src.rendering import render_position_png


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


def load_filter_config(config_path: Path) -> dict[str, int]:
    config = yaml.safe_load(config_path.read_text(encoding="utf-8"))
    filters = config["filters"]
    return {
        "min_fullmove": int(filters["min_fullmove"]),
        "max_fullmove": int(filters["max_fullmove"]),
        "min_remaining_pieces_per_side": int(filters["min_remaining_pieces_per_side"]),
    }


def render_eligible_positions(
    rows: list[dict[str, object]],
    image_dir: Path,
    *,
    board_size: int,
) -> dict[str, str]:
    image_dir.mkdir(parents=True, exist_ok=True)
    image_paths: dict[str, str] = {}
    for row in rows:
        title = "Eligible Middlegame Position"
        subtitle = (
            f"{row['white']} vs {row['black']} | Result {row['result']} | "
            f"Last move {row['lastmove_san']} ({row['lastmove_uci']})"
        )
        footer = (
            f"Position: {row['position_id']} | Fullmove: {row['fullmove_number']} | "
            f"Turn: {row['side_to_move']} | White pieces: {row['remaining_white_pieces']} | "
            f"Black pieces: {row['remaining_black_pieces']} | FEN: {row['fen']}"
        )
        output_path = image_dir / f"{row['position_id']}.png"
        render_position_png(
            str(row["fen"]),
            output_path,
            position_id=str(row["position_id"]),
            title=title,
            subtitle=subtitle,
            footer=footer,
            lastmove_uci=str(row["lastmove_uci"]),
            board_size=board_size,
        )
        row["image_path"] = str(output_path)
        image_paths[str(row["position_id"])] = str(output_path)
    return image_paths


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--sample-pgn", default="data/raw/lichess_sample_10_games.pgn")
    parser.add_argument("--config", default="configs/experiments/first_full_test.template.yaml")
    parser.add_argument("--output-dir", default="outputs/runs/step_04_parse_filter")
    parser.add_argument("--board-size", type=int, default=520)
    args = parser.parse_args()

    pgn_path = Path(args.sample_pgn)
    config_path = Path(args.config)
    output_dir = Path(args.output_dir)
    parsed_dir = output_dir / "parsed"
    filtered_dir = output_dir / "filtered"
    metadata_dir = output_dir / "metadata"
    image_dir = output_dir / "images"

    filter_config = load_filter_config(config_path)
    games, positions = parse_games(pgn_path)
    position_filtering, eligible_positions, skip_summary = apply_middlegame_filter(
        positions,
        **filter_config,
    )

    image_paths = render_eligible_positions(
        eligible_positions,
        image_dir,
        board_size=args.board_size,
    )
    for row in position_filtering:
        row["image_path"] = image_paths.get(str(row["position_id"]), "")

    write_csv(parsed_dir / "games.csv", games)
    write_csv(parsed_dir / "positions.csv", positions)
    write_csv(metadata_dir / "position_filtering.csv", position_filtering)
    write_csv(filtered_dir / "middlegame_positions.csv", eligible_positions)

    skip_summary_path = metadata_dir / "skip_reason_summary.json"
    skip_summary_path.parent.mkdir(parents=True, exist_ok=True)
    skip_summary_path.write_text(json.dumps(skip_summary, indent=2) + "\n", encoding="utf-8")

    summary = {
        "timestamp_utc": datetime.now(timezone.utc).isoformat(),
        "source_pgn": str(pgn_path),
        "config_path": str(config_path),
        "game_count": len(games),
        "parsed_position_count": len(positions),
        "eligible_middlegame_count": len(eligible_positions),
        "rendered_image_count": len(image_paths),
        "paths": {
            "games_csv": str(parsed_dir / "games.csv"),
            "positions_csv": str(parsed_dir / "positions.csv"),
            "position_filtering_csv": str(metadata_dir / "position_filtering.csv"),
            "middlegame_positions_csv": str(filtered_dir / "middlegame_positions.csv"),
            "skip_reason_summary_json": str(skip_summary_path),
            "image_dir": str(image_dir),
        },
        "skip_summary": skip_summary,
    }
    (metadata_dir / "summary.json").write_text(json.dumps(summary, indent=2) + "\n", encoding="utf-8")
    print(json.dumps(summary, indent=2))


if __name__ == "__main__":
    main()
