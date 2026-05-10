#!/usr/bin/env python3
"""Run one complete reviewable experiment end to end."""

from __future__ import annotations

import argparse
import json
import subprocess
import sys
from datetime import datetime, timezone
from pathlib import Path

import yaml


REPO_ROOT = Path(__file__).resolve().parents[2]


def run_step(args: list[str]) -> None:
    subprocess.run(args, cwd=REPO_ROOT, check=True)


def load_config(path: Path) -> dict[str, object]:
    return yaml.safe_load(path.read_text(encoding="utf-8"))


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--config", required=True)
    parser.add_argument("--run-id", required=True)
    parser.add_argument("--model-type", default="rapid", choices=["rapid", "blitz"])
    parser.add_argument("--stockfish-movetime-ms", type=int, default=120)
    parser.add_argument("--stockfish-multipv", type=int, default=20)
    args = parser.parse_args()

    config_path = REPO_ROOT / args.config
    config = load_config(config_path)
    run_id = args.run_id

    download_cfg = config["lichess"]
    run_root = REPO_ROOT / "outputs" / "runs" / run_id
    review_root = REPO_ROOT / "outputs" / "reviews" / run_id
    site_root = REPO_ROOT / "outputs" / "sites" / run_id
    reports_root = REPO_ROOT / "outputs" / "reports"

    sample_pgn = REPO_ROOT / "data" / "raw" / f"{run_id}.pgn"
    sample_archive = REPO_ROOT / "data" / "raw" / f"{run_id}.partial.pgn.zst"
    manifest_json = REPO_ROOT / "data" / "manifests" / f"{run_id}.json"

    step02_root = run_root / "step_02_download"
    step04_root = run_root / "step_04_parse_filter"
    step06_root = run_root / "step_06_policy_expansion"
    step07_root = run_root / "step_07_complexity_scoring"

    run_step(
        [
            sys.executable,
            "scripts/pipeline/download_lichess_games.py",
            "--source-url",
            str(download_cfg["source_url"]),
            "--target-games",
            str(download_cfg["game_count"]),
            "--candidate-games",
            str(download_cfg.get("candidate_games", download_cfg["game_count"])),
            "--sampling-mode",
            str(download_cfg.get("sampling_mode", "first_n")),
            "--initial-bytes",
            str(download_cfg.get("initial_bytes", 5 * 1024 * 1024)),
            "--max-bytes",
            str(download_cfg.get("max_bytes", 80 * 1024 * 1024)),
            "--raw-output",
            str(sample_pgn),
            "--archive-output",
            str(sample_archive),
            "--manifest-output",
            str(manifest_json),
        ]
    )

    step02_root.mkdir(parents=True, exist_ok=True)
    (step02_root / "metadata").mkdir(parents=True, exist_ok=True)
    manifest_copy = step02_root / "metadata" / "download_manifest.json"
    manifest_copy.write_text(manifest_json.read_text(encoding="utf-8"), encoding="utf-8")

    run_step(
        [
            sys.executable,
            "scripts/pipeline/parse_and_filter_positions.py",
            "--sample-pgn",
            str(sample_pgn),
            "--config",
            str(config_path),
            "--output-dir",
            str(step04_root),
        ]
    )
    run_step(
        [
            sys.executable,
            "scripts/pipeline/run_policy_expansion.py",
            "--positions-csv",
            str(step04_root / "filtered" / "middlegame_positions.csv"),
            "--config",
            str(config_path),
            "--output-dir",
            str(step06_root),
            "--model-type",
            args.model_type,
        ]
    )
    run_step(
        [
            sys.executable,
            "scripts/pipeline/score_complexity.py",
            "--positions-csv",
            str(step04_root / "filtered" / "middlegame_positions.csv"),
            "--raw-policy-jsonl",
            str(step06_root / "policy" / "raw_policy_snapshots.jsonl"),
            "--failed-inferences-csv",
            str(step06_root / "metadata" / "failed_inferences.csv"),
            "--config",
            str(config_path),
            "--output-dir",
            str(step07_root),
        ]
    )
    run_step(
        [
            sys.executable,
            "scripts/review/build_review_bundle.py",
            "--high-complexity-csv",
            str(step07_root / "complexity" / "high_complexity_positions.csv"),
            "--position-scores-csv",
            str(step07_root / "complexity" / "position_scores.csv"),
            "--step04-summary-json",
            str(step04_root / "metadata" / "summary.json"),
            "--step06-summary-json",
            str(step06_root / "metadata" / "summary.json"),
            "--step07-summary-json",
            str(step07_root / "metadata" / "summary.json"),
            "--output-dir",
            str(review_root),
        ]
    )
    run_step(
        [
            sys.executable,
            "scripts/review/build_review_site.py",
            "--games-csv",
            str(step04_root / "parsed" / "games.csv"),
            "--parsed-positions-csv",
            str(step04_root / "parsed" / "positions.csv"),
            "--position-scores-csv",
            str(step07_root / "complexity" / "position_scores.csv"),
            "--raw-policy-jsonl",
            str(step06_root / "policy" / "raw_policy_snapshots.jsonl"),
            "--run-summary-json",
            str(review_root / "metadata" / "run_summary.json"),
            "--board-images-dir",
            str(step04_root / "images"),
            "--output-dir",
            str(site_root),
            "--movetime-ms",
            str(args.stockfish_movetime_ms),
            "--multipv",
            str(args.stockfish_multipv),
        ]
    )

    report_json = reports_root / f"{run_id}.json"
    report_md = reports_root / f"{run_id}.md"
    run_step(
        [
            sys.executable,
            "scripts/pipeline/report_experiment_stats.py",
            "--site-bundle-json",
            str(site_root / "site" / "data" / "site_bundle.json"),
            "--output-json",
            str(report_json),
            "--output-md",
            str(report_md),
        ]
    )

    summary = {
        "generated_at": datetime.now(timezone.utc).isoformat(),
        "run_id": run_id,
        "config_path": str(config_path),
        "sample_pgn": str(sample_pgn),
        "manifest_json": str(manifest_json),
        "run_root": str(run_root),
        "review_root": str(review_root),
        "site_root": str(site_root),
        "report_json": str(report_json),
        "report_md": str(report_md),
        "browse_url": "http://127.0.0.1:8765",
    }
    print(json.dumps(summary, indent=2))


if __name__ == "__main__":
    main()
