#!/usr/bin/env python3
"""Run a Stockfish time-budget sweep on a pilot set of complex positions."""

from __future__ import annotations

import argparse
import json
import sys
from datetime import datetime, timezone
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parents[2]
if str(REPO_ROOT) not in sys.path:
    sys.path.insert(0, str(REPO_ROOT))

from src.analysis.time_budget_sweep import (
    load_yaml,
    read_csv_rows,
    run_time_budget_sweep,
    write_csv,
    write_json,
    write_jsonl,
)


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--config", required=True)
    parser.add_argument("--output-dir", default="")
    parser.add_argument(
        "--position-scores-csv",
        default="outputs/runs/20260509_balanced_100_games/step_07_complexity_scoring/complexity/position_scores.csv",
    )
    parser.add_argument(
        "--parsed-positions-csv",
        default="outputs/runs/20260509_balanced_100_games/step_04_parse_filter/parsed/positions.csv",
    )
    args = parser.parse_args()

    config_path = REPO_ROOT / args.config
    config = load_yaml(config_path)
    output_cfg = config["outputs"]
    analysis_id = str(output_cfg["analysis_id"])
    output_dir = REPO_ROOT / args.output_dir if args.output_dir else REPO_ROOT / str(output_cfg["save_root"]) / analysis_id
    analysis_dir = output_dir / "stockfish_time_budget"
    tables_dir = analysis_dir / "tables"
    metadata_dir = analysis_dir / "metadata"

    score_rows = read_csv_rows(REPO_ROOT / args.position_scores_csv)
    parsed_positions = read_csv_rows(REPO_ROOT / args.parsed_positions_csv)
    result = run_time_budget_sweep(
        score_rows=score_rows,
        parsed_positions=parsed_positions,
        analysis_config=config,
    )

    write_csv(tables_dir / "selected_positions.csv", result["selected_rows"])
    write_csv(tables_dir / "position_stability.csv", result["stability_rows"])
    write_csv(tables_dir / "root_analysis_by_budget.csv", result["budget_rows"])
    write_jsonl(analysis_dir / "root_analysis_by_budget.jsonl", result["budget_rows"])

    summary = {
        "generated_at": datetime.now(timezone.utc).isoformat(),
        "config_path": str(config_path),
        "position_scores_csv": str(REPO_ROOT / args.position_scores_csv),
        "parsed_positions_csv": str(REPO_ROOT / args.parsed_positions_csv),
        **result["summary"],
        "paths": {
            "selected_positions_csv": str(tables_dir / "selected_positions.csv"),
            "position_stability_csv": str(tables_dir / "position_stability.csv"),
            "root_analysis_by_budget_csv": str(tables_dir / "root_analysis_by_budget.csv"),
            "root_analysis_by_budget_jsonl": str(analysis_dir / "root_analysis_by_budget.jsonl"),
        },
    }
    write_json(metadata_dir / "summary.json", summary)
    (metadata_dir / "summary.md").write_text(
        "\n".join(
            [
                "# Stockfish Time-Budget Sweep Pilot",
                "",
                f"- Analysis id: `{summary['analysis_id']}`",
                f"- Selected game: `{summary['selected_game_id']}`",
                f"- Game label: `{summary['game_label']}`",
                f"- Positions analysed: `{summary['selected_position_count']}`",
                f"- Budgets (ms): `{summary['budgets_ms']}`",
                f"- Parallel workers: `{summary['parallel']['max_workers']}`",
                f"- Stockfish threads / worker: `{summary['parallel']['stockfish_threads_per_worker']}`",
                f"- MultiPV: `{summary['parallel']['multipv']}`",
                f"- Best-move switch mean: `{summary['best_move_switch_stats']['mean']}`",
                f"- Best-score range mean (cp): `{summary['best_score_range_stats']['mean']}`",
                f"- Actual-move rank range mean: `{summary['actual_move_rank_range_stats']['mean']}`",
                "",
            ]
        )
        + "\n",
        encoding="utf-8",
    )
    print(json.dumps(summary, indent=2))


if __name__ == "__main__":
    main()
