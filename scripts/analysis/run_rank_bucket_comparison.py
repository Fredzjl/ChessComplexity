#!/usr/bin/env python3
"""Run experiment 2: actual-move rank comparison by Elo bucket."""

from __future__ import annotations

import argparse
import json
import sys
from datetime import datetime, timezone
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parents[2]
if str(REPO_ROOT) not in sys.path:
    sys.path.insert(0, str(REPO_ROOT))

from src.analysis.rank_bucket_comparison import (
    actual_move_lookup,
    build_bucket_summary_rows,
    build_position_level_rows,
    build_stockfish_cache,
    build_summary_payload,
    load_raw_snapshots,
    load_stockfish_cache,
    load_yaml,
    read_csv_rows,
    scoped_position_rows,
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
    analysis_dir = output_dir / "rank_bucket_comparison"
    tables_dir = analysis_dir / "tables"
    metadata_dir = analysis_dir / "metadata"
    cache_dir = analysis_dir / "cache"

    score_rows = read_csv_rows(REPO_ROOT / args.position_scores_csv)
    parsed_positions = read_csv_rows(REPO_ROOT / args.parsed_positions_csv)
    actual_lookup = actual_move_lookup(parsed_positions)
    scoped_rows = scoped_position_rows(
        score_rows=score_rows,
        actual_lookup=actual_lookup,
        min_player_elo=int(config["population"]["min_player_elo"]),
    )

    stockfish_cfg = config["models"]["stockfish"]
    cache_path = cache_dir / "stockfish_root_analysis.json"
    stockfish_cache = build_stockfish_cache(
        position_rows=score_rows,
        cache_path=cache_path,
        binary_path=stockfish_cfg.get("binary_path"),
        movetime_ms=int(stockfish_cfg["movetime_ms"]),
        multipv=int(stockfish_cfg["multipv"]),
        threads_per_worker=int(stockfish_cfg.get("threads_per_worker", 1)),
        max_workers=int(stockfish_cfg.get("max_workers", 4)) if stockfish_cfg.get("max_workers") != "auto" else max(1, min(8, len(score_rows))),
        hash_mb=int(stockfish_cfg.get("hash_mb", 128)),
        refresh_cache=bool(stockfish_cfg.get("refresh_cache", False)),
    )

    root_snapshots = load_raw_snapshots(REPO_ROOT / args.raw_policy_jsonl)
    position_rows = build_position_level_rows(
        scoped_rows=scoped_rows,
        root_snapshots=root_snapshots,
        stockfish_cache=stockfish_cache,
        elo_bucket_width=int(config["population"]["elo_bucket_width"]),
    )
    bucket_rows = build_bucket_summary_rows(position_rows=position_rows)
    summary_payload = build_summary_payload(
        config=config,
        bucket_rows=bucket_rows,
        position_rows=position_rows,
    )

    write_csv(tables_dir / "position_level_ranks.csv", position_rows)
    write_csv(tables_dir / "bucket_summary.csv", bucket_rows)
    write_csv(tables_dir / "chart_ready_long.csv", bucket_rows)
    write_json(metadata_dir / "summary.json", summary_payload)
    (metadata_dir / "summary.md").write_text(
        "\n".join(
            [
                "# Rank Bucket Comparison",
                "",
                f"- Generated at: `{datetime.now(timezone.utc).isoformat()}`",
                f"- Analysis id: `{analysis_id}`",
                f"- Scoped positions: `{summary_payload['scoped_position_count']}`",
                f"- Elo floor: `{summary_payload['min_player_elo']}`",
                f"- Bucket width: `{summary_payload['elo_bucket_width']}`",
                f"- Stockfish movetime: `{summary_payload['stockfish']['movetime_ms']}` ms",
                f"- Stockfish MultiPV: `{summary_payload['stockfish']['multipv']}`",
                "",
                "## All eligible",
                "",
                f"- Maia mean rank: `{summary_payload['slices']['all_eligible']['maia'].get('mean_rank')}`",
                f"- Stockfish clipped mean rank: `{summary_payload['slices']['all_eligible']['stockfish'].get('mean_rank_topk_clipped')}`",
                f"- Stockfish coverage: `{summary_payload['slices']['all_eligible']['stockfish'].get('coverage')}`",
                "",
                "## High complexity",
                "",
                f"- Maia mean rank: `{summary_payload['slices']['high_complexity']['maia'].get('mean_rank')}`",
                f"- Stockfish clipped mean rank: `{summary_payload['slices']['high_complexity']['stockfish'].get('mean_rank_topk_clipped')}`",
                f"- Stockfish coverage: `{summary_payload['slices']['high_complexity']['stockfish'].get('coverage')}`",
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
            "stockfish_analysis_json": str(cache_path),
            "position_level_ranks_csv": str(tables_dir / "position_level_ranks.csv"),
            "bucket_summary_csv": str(tables_dir / "bucket_summary.csv"),
            "chart_ready_long_csv": str(tables_dir / "chart_ready_long.csv"),
            "summary_json": str(metadata_dir / "summary.json"),
            "summary_md": str(metadata_dir / "summary.md"),
        },
        "summary": summary_payload,
    }
    print(json.dumps(run_summary, indent=2))


if __name__ == "__main__":
    main()
