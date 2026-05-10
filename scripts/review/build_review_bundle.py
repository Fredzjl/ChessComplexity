#!/usr/bin/env python3
"""Build a manual-review bundle for the first complete experiment run."""

from __future__ import annotations

import argparse
import csv
import json
import shutil
import sys
from collections import Counter, defaultdict
from datetime import datetime, timezone
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parents[2]
if str(REPO_ROOT) not in sys.path:
    sys.path.insert(0, str(REPO_ROOT))


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


def sort_high_rows(rows: list[dict[str, str]]) -> list[dict[str, str]]:
    return sorted(
        rows,
        key=lambda row: (-int(row["complexity_score"]), row["game_id"], int(row["ply_index"])),
    )


def add_rank(rows: list[dict[str, str]]) -> list[dict[str, object]]:
    ranked: list[dict[str, object]] = []
    for rank, row in enumerate(rows, start=1):
        enriched = dict(row)
        enriched["rank"] = rank
        ranked.append(enriched)
    return ranked


def build_per_game_examples(rows: list[dict[str, str]], *, per_game_limit: int) -> list[dict[str, object]]:
    per_game: defaultdict[str, list[dict[str, str]]] = defaultdict(list)
    for row in rows:
        per_game[row["game_id"]].append(row)

    output: list[dict[str, object]] = []
    for game_id in sorted(per_game):
        game_rows = sort_high_rows(per_game[game_id])[:per_game_limit]
        for local_rank, row in enumerate(game_rows, start=1):
            enriched = dict(row)
            enriched["game_local_rank"] = local_rank
            output.append(enriched)
    return output


def build_game_summary(rows: list[dict[str, str]]) -> list[dict[str, object]]:
    per_game: defaultdict[str, list[dict[str, str]]] = defaultdict(list)
    for row in rows:
        per_game[row["game_id"]].append(row)

    summary_rows: list[dict[str, object]] = []
    for game_id in sorted(per_game):
        game_rows = sort_high_rows(per_game[game_id])
        scores = [int(row["complexity_score"]) for row in game_rows]
        top_row = game_rows[0]
        summary_rows.append(
            {
                "game_id": game_id,
                "high_complexity_position_count": len(game_rows),
                "max_complexity_score": max(scores),
                "min_complexity_score": min(scores),
                "mean_complexity_score": round(sum(scores) / len(scores), 4),
                "top_position_id": top_row["position_id"],
                "top_image_path": top_row["image_path"],
            }
        )
    return summary_rows


def existing_artifacts(paths: dict[str, str]) -> dict[str, bool]:
    return {name: Path(path).exists() for name, path in paths.items()}


def copy_shortlist_images(rows: list[dict[str, object]], output_dir: Path) -> list[dict[str, object]]:
    output_dir.mkdir(parents=True, exist_ok=True)
    copied: list[dict[str, object]] = []
    for row in rows:
        source = Path(str(row["image_path"]))
        target = output_dir / source.name
        if source.exists():
            shutil.copy2(source, target)
        enriched = dict(row)
        enriched["review_image_path"] = str(target)
        copied.append(enriched)
    return copied


def write_markdown_summary(
    path: Path,
    *,
    run_summary: dict[str, object],
    top_rows: list[dict[str, object]],
    per_game_examples: list[dict[str, object]],
    artifact_paths: dict[str, str],
    missing_image_count: int,
) -> None:
    lines = [
        "# Final Run Summary",
        "",
        "## Counts",
        "",
        f"- Eligible middlegame positions: `{run_summary['eligible_middlegame_count']}`",
        f"- Successful policy roots: `{run_summary['successful_root_positions']}`",
        f"- Failed policy roots: `{run_summary['failed_root_positions']}`",
        f"- Successfully scored positions: `{run_summary['successful_scores']}`",
        f"- High-complexity positions: `{run_summary['high_complexity_count']}`",
        "",
        "## Thresholds",
        "",
        f"- Move probability threshold: `{run_summary['min_probability']}`",
        f"- Expansion plies: `{run_summary['expansion_plies']}`",
        f"- High-complexity threshold: `{run_summary['high_complexity_threshold']}`",
        "",
        "## Primary Artifacts",
        "",
    ]
    for name, artifact_path in artifact_paths.items():
        lines.append(f"- `{name}`: `{artifact_path}`")

    lines.extend(
        [
            "",
            "## Top High-Complexity Positions",
            "",
        ]
    )
    for row in top_rows[:10]:
        lines.append(
            f"- `{row['position_id']}` score `{row['complexity_score']}` image `{row['image_path']}`"
        )

    lines.extend(
        [
            "",
            "## Per-Game Examples",
            "",
        ]
    )
    for row in per_game_examples[:20]:
        lines.append(
            f"- `{row['game_id']}` local rank `{row['game_local_rank']}`: `{row['position_id']}` score `{row['complexity_score']}`"
        )

    lines.extend(
        [
            "",
            "## Weak Assumptions and Edge Cases",
            "",
            f"- The current `complexity_score >= {run_summary['high_complexity_threshold']}` threshold may still be permissive for larger runs.",
            "- The metric counts all qualifying edges equally and does not yet distinguish forcing lines from quiet branching.",
            f"- `{run_summary['failed_root_positions']}` positions failed Maia-2 inference and remain excluded from score computation.",
            f"- Missing review images detected: `{missing_image_count}`",
            "",
            "## Recommendation",
            "",
            "- Next, manually inspect the shortlist images and compare them against the saved policy distributions before tightening the threshold or redesigning the score.",
            "",
        ]
    )
    path.write_text("\n".join(lines) + "\n", encoding="utf-8")


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument(
        "--high-complexity-csv",
        default="outputs/runs/step_07_complexity_scoring/complexity/high_complexity_positions.csv",
    )
    parser.add_argument(
        "--position-scores-csv",
        default="outputs/runs/step_07_complexity_scoring/complexity/position_scores.csv",
    )
    parser.add_argument(
        "--step04-summary-json",
        default="outputs/runs/step_04_parse_filter/metadata/summary.json",
    )
    parser.add_argument(
        "--step06-summary-json",
        default="outputs/runs/step_06_policy_expansion/metadata/summary.json",
    )
    parser.add_argument(
        "--step07-summary-json",
        default="outputs/runs/step_07_complexity_scoring/metadata/summary.json",
    )
    parser.add_argument("--output-dir", default="outputs/reviews/step_08_review_bundle")
    parser.add_argument("--top-limit", type=int, default=40)
    parser.add_argument("--per-game-limit", type=int, default=3)
    args = parser.parse_args()

    high_csv = Path(args.high_complexity_csv)
    scores_csv = Path(args.position_scores_csv)
    step04_summary = json.loads(Path(args.step04_summary_json).read_text(encoding="utf-8"))
    step06_summary = json.loads(Path(args.step06_summary_json).read_text(encoding="utf-8"))
    step07_summary = json.loads(Path(args.step07_summary_json).read_text(encoding="utf-8"))
    output_dir = Path(args.output_dir)
    review_dir = output_dir / "review"
    metadata_dir = output_dir / "metadata"
    shortlist_image_dir = review_dir / "shortlist_images"

    high_rows = sort_high_rows(read_csv_rows(high_csv))
    ranked_high_rows = add_rank(high_rows)
    top_rows = ranked_high_rows[: args.top_limit]
    per_game_examples = build_per_game_examples(high_rows, per_game_limit=args.per_game_limit)
    game_summary_rows = build_game_summary(high_rows)

    missing_image_rows = [row for row in high_rows if not Path(row["image_path"]).exists()]
    missing_image_count = len(missing_image_rows)

    ranked_top_rows = copy_shortlist_images(top_rows, shortlist_image_dir)
    per_game_examples_with_images = copy_shortlist_images(per_game_examples, shortlist_image_dir)

    top_table_path = review_dir / "top_high_complexity_review.csv"
    per_game_path = review_dir / "per_game_examples.csv"
    game_summary_path = review_dir / "game_summary.csv"
    missing_images_path = metadata_dir / "missing_images.csv"
    write_csv(top_table_path, ranked_top_rows)
    write_csv(per_game_path, per_game_examples_with_images)
    write_csv(game_summary_path, game_summary_rows)
    write_csv(missing_images_path, missing_image_rows)

    artifact_paths = {
        "position_scores_csv": str(scores_csv),
        "high_complexity_positions_csv": str(high_csv),
        "top_high_complexity_review_csv": str(top_table_path),
        "per_game_examples_csv": str(per_game_path),
        "game_summary_csv": str(game_summary_path),
        "review_shortlist_image_dir": str(shortlist_image_dir),
        "step_06_raw_policy_jsonl": step06_summary["paths"]["raw_policy_snapshots_jsonl"],
        "step_06_topk_policy_csv": step06_summary["paths"]["topk_policy_snapshots_csv"],
    }

    artifact_existence = existing_artifacts(artifact_paths)
    run_summary = {
        "timestamp_utc": datetime.now(timezone.utc).isoformat(),
        "eligible_middlegame_count": step04_summary["eligible_middlegame_count"],
        "successful_root_positions": step06_summary["successful_root_positions"],
        "failed_root_positions": step06_summary["failed_root_positions"],
        "successful_scores": step07_summary["successful_scores"],
        "failed_scores": step07_summary["failed_scores"],
        "high_complexity_count": step07_summary["high_complexity_count"],
        "min_probability": step07_summary["expansion"]["min_probability"],
        "expansion_plies": step07_summary["expansion"]["expansion_plies"],
        "high_complexity_threshold": step07_summary["threshold"],
        "missing_image_count": missing_image_count,
        "artifact_paths": artifact_paths,
        "artifact_exists": artifact_existence,
        "top_shortlist_count": len(ranked_top_rows),
        "per_game_example_count": len(per_game_examples_with_images),
        "games_with_high_complexity": len(game_summary_rows),
        "score_distribution": step07_summary["score_distribution"],
        "top_high_complexity_preview": step07_summary["top_high_complexity_preview"],
    }
    metadata_dir.mkdir(parents=True, exist_ok=True)
    (metadata_dir / "run_summary.json").write_text(json.dumps(run_summary, indent=2) + "\n", encoding="utf-8")

    write_markdown_summary(
        metadata_dir / "run_summary.md",
        run_summary=run_summary,
        top_rows=ranked_top_rows,
        per_game_examples=per_game_examples_with_images,
        artifact_paths=artifact_paths,
        missing_image_count=missing_image_count,
    )

    print(json.dumps(run_summary, indent=2))


if __name__ == "__main__":
    main()
