#!/usr/bin/env python3
"""Export high-level experiment statistics from a built review site bundle."""

from __future__ import annotations

import argparse
import json
from datetime import datetime, timezone
from pathlib import Path


def write_report(path: Path, payload: dict[str, object]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(payload, indent=2) + "\n", encoding="utf-8")


def write_markdown(path: Path, payload: dict[str, object]) -> None:
    lines = [
        "# Experiment Stats",
        "",
        f"- Generated at: `{payload['generated_at']}`",
        f"- Site bundle: `{payload['site_bundle_path']}`",
        f"- Games: `{payload['game_count']}`",
        f"- Eligible middlegame positions: `{payload['eligible_middlegame_count']}`",
        f"- High-complexity positions: `{payload['high_complexity_count']}`",
        f"- Maia average actual-move rank: `{payload['maia_actual_move_rank_mean']}` (coverage `{payload['maia_actual_move_rank_coverage']}`)",
        f"- Stockfish average actual-move rank: `{payload['stockfish_actual_move_rank_mean']}` (coverage `{payload['stockfish_actual_move_rank_coverage']}`)",
        "",
    ]
    path.write_text("\n".join(lines), encoding="utf-8")


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--site-bundle-json", required=True)
    parser.add_argument("--output-json", required=True)
    parser.add_argument("--output-md", required=True)
    args = parser.parse_args()

    site_bundle_path = Path(args.site_bundle_json)
    bundle = json.loads(site_bundle_path.read_text(encoding="utf-8"))
    summary = bundle["summary"]

    payload = {
        "generated_at": datetime.now(timezone.utc).isoformat(),
        "site_bundle_path": str(site_bundle_path),
        "game_count": len(bundle["games"]),
        "eligible_middlegame_count": summary["eligible_middlegame_count"],
        "high_complexity_count": summary["high_complexity_count"],
        "maia_actual_move_rank_mean": summary.get("maia_actual_move_rank_mean"),
        "maia_actual_move_rank_coverage": summary.get("maia_actual_move_rank_coverage"),
        "stockfish_actual_move_rank_mean": summary.get("stockfish_actual_move_rank_mean"),
        "stockfish_actual_move_rank_coverage": summary.get("stockfish_actual_move_rank_coverage"),
    }
    write_report(Path(args.output_json), payload)
    write_markdown(Path(args.output_md), payload)
    print(json.dumps(payload, indent=2))


if __name__ == "__main__":
    main()
