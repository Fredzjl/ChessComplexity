#!/usr/bin/env python3
"""Run experiment 3: realizability probe for candidate moves."""

from __future__ import annotations

import argparse
import json
import sys
from datetime import datetime, timezone
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parents[2]
if str(REPO_ROOT) not in sys.path:
    sys.path.insert(0, str(REPO_ROOT))

from src.analysis.realizability import (
    load_root_snapshots,
    load_yaml,
    read_csv_rows,
    run_realizability_probe,
    write_csv,
    write_json,
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
    parser.add_argument(
        "--raw-policy-jsonl",
        default="outputs/runs/20260509_balanced_100_games/step_06_policy_expansion/policy/raw_policy_snapshots.jsonl",
    )
    args = parser.parse_args()

    config_path = REPO_ROOT / args.config
    config = load_yaml(config_path)
    analysis_id = str(config["outputs"]["analysis_id"])
    output_dir = REPO_ROOT / args.output_dir if args.output_dir else REPO_ROOT / str(config["outputs"]["save_root"]) / analysis_id
    analysis_dir = output_dir / "realizability_probe"
    tables_dir = analysis_dir / "tables"
    metadata_dir = analysis_dir / "metadata"

    score_rows = read_csv_rows(REPO_ROOT / args.position_scores_csv)
    parsed_positions = read_csv_rows(REPO_ROOT / args.parsed_positions_csv)
    root_snapshots = load_root_snapshots(REPO_ROOT / args.raw_policy_jsonl)

    scoped_positions, position_rows, candidate_rows, bucket_rows, summary_payload = run_realizability_probe(
        config=config,
        score_rows=score_rows,
        parsed_positions=parsed_positions,
        root_snapshots=root_snapshots,
    )

    write_csv(tables_dir / "candidate_feature_table.csv", candidate_rows)
    write_csv(tables_dir / "position_summary.csv", position_rows)
    write_csv(tables_dir / "elo_bucket_summary.csv", bucket_rows)
    write_json(metadata_dir / "summary.json", summary_payload)
    (metadata_dir / "summary.md").write_text(
        "\n".join(
            [
                "# Realizability Probe",
                "",
                f"- Generated at: `{datetime.now(timezone.utc).isoformat()}`",
                f"- Analysis id: `{analysis_id}`",
                f"- Scoped positions: `{len(scoped_positions)}`",
                f"- Candidate rows: `{len(candidate_rows)}`",
                f"- Mean candidate realizability: `{summary_payload.get('mean_candidate_realizability')}`",
                f"- Mean actual-move realizability: `{summary_payload.get('mean_actual_realizability')}`",
                f"- Mean engine-best realizability: `{summary_payload.get('mean_engine_best_realizability')}`",
                f"- Actual minus engine-best mean: `{summary_payload.get('mean_actual_minus_engine_best')}`",
                f"- Maia probability / realizability correlation: `{summary_payload.get('candidate_level_maia_probability_realizability_corr')}`",
                "",
            ]
        )
        + "\n",
        encoding="utf-8",
    )

    run_summary = {
        "generated_at": datetime.now(timezone.utc).isoformat(),
        "analysis_id": analysis_id,
        "config_path": str(config_path),
        "paths": {
            "candidate_feature_table_csv": str(tables_dir / "candidate_feature_table.csv"),
            "position_summary_csv": str(tables_dir / "position_summary.csv"),
            "elo_bucket_summary_csv": str(tables_dir / "elo_bucket_summary.csv"),
            "summary_json": str(metadata_dir / "summary.json"),
            "summary_md": str(metadata_dir / "summary.md"),
        },
        "summary": summary_payload,
    }
    print(json.dumps(run_summary, indent=2))


if __name__ == "__main__":
    main()
