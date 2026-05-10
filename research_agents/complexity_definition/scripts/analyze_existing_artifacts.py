#!/usr/bin/env python3
"""Summarize existing repository artifacts for the complexity-definition study."""

from __future__ import annotations

import argparse
import csv
import json
import math
import statistics
from pathlib import Path
from typing import Any


def load_bundle(path: Path) -> dict[str, Any]:
    return json.loads(path.read_text(encoding="utf-8"))


def write_json(path: Path, payload: object) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(payload, indent=2, ensure_ascii=False) + "\n", encoding="utf-8")


def write_csv(path: Path, rows: list[dict[str, object]]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    if not rows:
        path.write_text("", encoding="utf-8")
        return
    with path.open("w", encoding="utf-8", newline="") as handle:
        writer = csv.DictWriter(handle, fieldnames=list(rows[0].keys()))
        writer.writeheader()
        writer.writerows(rows)


def rounded(value: float | None, digits: int = 4) -> float | None:
    if value is None:
        return None
    return round(float(value), digits)


def safe_mean(values: list[int | float]) -> float | None:
    if not values:
        return None
    return float(statistics.mean(values))


def safe_median(values: list[int | float]) -> float | None:
    if not values:
        return None
    return float(statistics.median(values))


def non_null_numeric(values: list[Any]) -> list[float]:
    return [float(value) for value in values if value is not None]


def pearson(xs: list[float], ys: list[float]) -> float | None:
    if len(xs) < 2 or len(xs) != len(ys):
        return None
    x_mean = statistics.mean(xs)
    y_mean = statistics.mean(ys)
    numerator = sum((x - x_mean) * (y - y_mean) for x, y in zip(xs, ys))
    denom_x = math.sqrt(sum((x - x_mean) ** 2 for x in xs))
    denom_y = math.sqrt(sum((y - y_mean) ** 2 for y in ys))
    if denom_x == 0 or denom_y == 0:
        return None
    return float(numerator / (denom_x * denom_y))


def rank_stats(ranks: list[int | None], total_count: int) -> dict[str, object]:
    covered = [rank for rank in ranks if rank is not None]
    return {
        "total_positions": total_count,
        "coverage_count": len(covered),
        "coverage_rate": rounded(len(covered) / total_count if total_count else None),
        "mean_rank": rounded(safe_mean(covered)),
        "median_rank": rounded(safe_median(covered)),
        "hit_at_1": rounded(sum(rank == 1 for rank in covered) / total_count if total_count else None),
        "hit_at_3": rounded(sum(rank <= 3 for rank in covered) / total_count if total_count else None),
        "hit_at_5": rounded(sum(rank <= 5 for rank in covered) / total_count if total_count else None),
    }


def complexity_bucket(score: int) -> str:
    if score < 10:
        return "0-9"
    if score < 20:
        return "10-19"
    if score < 30:
        return "20-29"
    if score < 40:
        return "30-39"
    return "40+"


def int_or_default(value: Any, default: int = 0) -> int:
    if value is None:
        return default
    return int(value)


def flatten_positions(bundle: dict[str, Any]) -> list[dict[str, Any]]:
    rows: list[dict[str, Any]] = []
    for game in bundle.get("games", []):
        for position in game.get("positions", []):
            actual_move = position.get("actual_move", {})
            complexity = position.get("complexity", {})
            conflicts = position.get("conflicts", {})
            time_budget = position.get("experiments", {}).get("time_budget", {})
            realizability = position.get("experiments", {}).get("realizability", {})
            reluctant = conflicts.get("engine_best_maia_reluctant", {})
            reluctant_engine_best = reluctant.get("engine_best") or {}

            rows.append(
                {
                    "position_id": position["position_id"],
                    "complexity_score": int_or_default(complexity.get("score"), 0),
                    "high_complexity": bool(complexity.get("high", False)),
                    "maia_rank": actual_move.get("model_rank"),
                    "stockfish_rank": actual_move.get("engine_rank"),
                    "time_budget_available": bool(time_budget.get("available", False)),
                    "time_budget_summary": time_budget.get("summary", {}),
                    "realizability_available": bool(realizability.get("available", False)),
                    "engine_best_maia_reluctant": bool(reluctant.get("flagged", False)),
                    "engine_best_score_cp": reluctant_engine_best.get("score_cp"),
                    "engine_best_actual_matches": reluctant_engine_best.get("actual_matches"),
                }
            )
    return rows


def compute_rank_tables(rows: list[dict[str, Any]]) -> tuple[list[dict[str, object]], dict[str, Any]]:
    slices = {
        "all": rows,
        "high_complexity": [row for row in rows if row["high_complexity"]],
        "non_high_complexity": [row for row in rows if not row["high_complexity"]],
    }
    table: list[dict[str, object]] = []
    summary: dict[str, Any] = {}
    for slice_name, slice_rows in slices.items():
        maia = rank_stats([row["maia_rank"] for row in slice_rows], len(slice_rows))
        stockfish = rank_stats([row["stockfish_rank"] for row in slice_rows], len(slice_rows))
        summary[slice_name] = {"maia": maia, "stockfish": stockfish}
        table.append({"slice": slice_name, "model": "maia", **maia})
        table.append({"slice": slice_name, "model": "stockfish_top20", **stockfish})

    high_maia = summary["high_complexity"]["maia"]["mean_rank"]
    nonhigh_maia = summary["non_high_complexity"]["maia"]["mean_rank"]
    high_sf = summary["high_complexity"]["stockfish"]["mean_rank"]
    nonhigh_sf = summary["non_high_complexity"]["stockfish"]["mean_rank"]
    summary["gaps"] = {
        "maia_mean_rank_high_minus_nonhigh": rounded(
            (high_maia - nonhigh_maia) if high_maia is not None and nonhigh_maia is not None else None
        ),
        "stockfish_mean_rank_high_minus_nonhigh": rounded(
            (high_sf - nonhigh_sf) if high_sf is not None and nonhigh_sf is not None else None
        ),
    }
    return table, summary


def compute_time_budget_tables(rows: list[dict[str, Any]]) -> tuple[list[dict[str, object]], dict[str, Any]]:
    eligible = [row for row in rows if row["time_budget_available"]]
    bucket_order = ["10-19", "20-29", "30-39", "40+"]
    table: list[dict[str, object]] = []
    overall_switches: list[float] = []
    overall_ranges: list[float] = []
    overall_scores: list[float] = []

    for bucket in bucket_order:
        bucket_rows = [row for row in eligible if complexity_bucket(int(row["complexity_score"])) == bucket]
        switches = [row["time_budget_summary"].get("best_move_switch_count", 0) for row in bucket_rows]
        ranges = [row["time_budget_summary"].get("best_score_range_cp", 0) for row in bucket_rows]
        overlaps = [row["time_budget_summary"].get("adjacent_top3_overlap_mean") for row in bucket_rows]
        pv_prefix = [row["time_budget_summary"].get("best_pv_prefix_mean_plies") for row in bucket_rows]
        unique_best_counts = [row["time_budget_summary"].get("unique_best_move_count", 0) for row in bucket_rows]

        overall_switches.extend(non_null_numeric(switches))
        overall_ranges.extend(non_null_numeric(ranges))
        overall_scores.extend(float(row["complexity_score"]) for row in bucket_rows)

        table.append(
            {
                "complexity_bucket": bucket,
                "position_count": len(bucket_rows),
                "mean_complexity_score": rounded(safe_mean([row["complexity_score"] for row in bucket_rows])),
                "mean_best_move_switch_count": rounded(safe_mean(non_null_numeric(switches))),
                "switch_rate_ge_1": rounded(sum(value >= 1 for value in switches) / len(bucket_rows) if bucket_rows else None),
                "switch_rate_ge_2": rounded(sum(value >= 2 for value in switches) / len(bucket_rows) if bucket_rows else None),
                "mean_unique_best_move_count": rounded(safe_mean(non_null_numeric(unique_best_counts))),
                "mean_best_score_range_cp": rounded(safe_mean(non_null_numeric(ranges))),
                "mean_adjacent_top3_overlap": rounded(safe_mean(non_null_numeric(overlaps))),
                "mean_pv_prefix_plies": rounded(safe_mean(non_null_numeric(pv_prefix))),
            }
        )

    switch_pairs = [
        (float(row["complexity_score"]), float(row["time_budget_summary"]["best_move_switch_count"]))
        for row in eligible
        if row["time_budget_summary"].get("best_move_switch_count") is not None
    ]
    range_pairs = [
        (float(row["complexity_score"]), float(row["time_budget_summary"]["best_score_range_cp"]))
        for row in eligible
        if row["time_budget_summary"].get("best_score_range_cp") is not None
    ]
    per_position_switches = [pair[1] for pair in switch_pairs]
    per_position_ranges = [pair[1] for pair in range_pairs]
    switch_scores = [pair[0] for pair in switch_pairs]
    range_scores = [pair[0] for pair in range_pairs]

    summary = {
        "eligible_complex_positions_with_time_budget": len(eligible),
        "mean_best_move_switch_count": rounded(safe_mean(per_position_switches)),
        "switch_rate_ge_1": rounded(sum(value >= 1 for value in per_position_switches) / len(eligible) if eligible else None),
        "switch_rate_ge_2": rounded(sum(value >= 2 for value in per_position_switches) / len(eligible) if eligible else None),
        "mean_best_score_range_cp": rounded(safe_mean(per_position_ranges)),
        "corr_complexity_vs_switch_count": rounded(pearson(switch_scores, per_position_switches)),
        "corr_complexity_vs_score_range_cp": rounded(pearson(range_scores, per_position_ranges)),
    }
    return table, summary


def compute_reluctance_tables(rows: list[dict[str, Any]]) -> tuple[list[dict[str, object]], dict[str, Any]]:
    slices = {
        "all": rows,
        "high_complexity": [row for row in rows if row["high_complexity"]],
        "non_high_complexity": [row for row in rows if not row["high_complexity"]],
    }
    table: list[dict[str, object]] = []
    summary: dict[str, Any] = {}

    for slice_name, slice_rows in slices.items():
        strong_rows = [
            row
            for row in slice_rows
            if row["engine_best_score_cp"] is not None and int(row["engine_best_score_cp"]) >= 300
        ]
        flagged_rows = [row for row in strong_rows if row["engine_best_maia_reluctant"]]
        human_played_anyway = [
            row
            for row in flagged_rows
            if bool(row["engine_best_actual_matches"])
        ]
        result = {
            "slice": slice_name,
            "strong_engine_positions": len(strong_rows),
            "flagged_reluctant_positions": len(flagged_rows),
            "flagged_rate_within_strong": rounded(len(flagged_rows) / len(strong_rows) if strong_rows else None),
            "human_played_anyway_count": len(human_played_anyway),
            "human_played_anyway_rate_within_flagged": rounded(
                len(human_played_anyway) / len(flagged_rows) if flagged_rows else None
            ),
        }
        table.append(result)
        summary[slice_name] = result

    return table, summary


def build_markdown(
    *,
    bundle_path: Path,
    bundle_summary: dict[str, Any],
    rank_summary: dict[str, Any],
    time_summary: dict[str, Any],
    reluctance_summary: dict[str, Any],
) -> str:
    lines = [
        "# Existing Artifact Validation Summary",
        "",
        "## Scope",
        "",
        f"- Source bundle: `{bundle_path}`",
        f"- Positions in bundle: `{bundle_summary['position_count']}`",
        f"- High-complexity positions: `{bundle_summary['high_complexity_count']}`",
        f"- Non-high-complexity positions: `{bundle_summary['non_high_complexity_count']}`",
        "",
        "## Verified Results",
        "",
        "### 1. Actual human-move rank is worse in complex positions",
        "",
        f"- Maia mean rank: `{rank_summary['high_complexity']['maia']['mean_rank']}` in high-complexity vs `{rank_summary['non_high_complexity']['maia']['mean_rank']}` in non-high-complexity.",
        f"- Stockfish mean rank: `{rank_summary['high_complexity']['stockfish']['mean_rank']}` in high-complexity vs `{rank_summary['non_high_complexity']['stockfish']['mean_rank']}` in non-high-complexity.",
        f"- Maia hit@1: `{rank_summary['high_complexity']['maia']['hit_at_1']}` vs `{rank_summary['non_high_complexity']['maia']['hit_at_1']}`.",
        f"- Stockfish hit@1: `{rank_summary['high_complexity']['stockfish']['hit_at_1']}` vs `{rank_summary['non_high_complexity']['stockfish']['hit_at_1']}`.",
        "",
        "### 2. Stockfish changes its mind frequently across time budgets on complex positions",
        "",
        f"- Complex positions with time-budget traces: `{time_summary['eligible_complex_positions_with_time_budget']}`.",
        f"- Mean best-move switch count across 6 budgets: `{time_summary['mean_best_move_switch_count']}`.",
        f"- Share with at least one best-move switch: `{time_summary['switch_rate_ge_1']}`.",
        f"- Share with at least two switches: `{time_summary['switch_rate_ge_2']}`.",
        f"- Correlation between complexity score and switch count: `{time_summary['corr_complexity_vs_switch_count']}`.",
        f"- Correlation between complexity score and best-score range: `{time_summary['corr_complexity_vs_score_range_cp']}`.",
        "",
        "### 3. Strong Stockfish recommendations that Maia dislikes do exist",
        "",
        f"- Strong-engine positions overall (`Stockfish >= +3.00`): `{reluctance_summary['all']['strong_engine_positions']}`.",
        f"- Maia-reluctant among those: `{reluctance_summary['all']['flagged_reluctant_positions']}` (`{reluctance_summary['all']['flagged_rate_within_strong']}`).",
        f"- High-complexity flagged rate within strong-engine positions: `{reluctance_summary['high_complexity']['flagged_rate_within_strong']}`.",
        f"- Non-high-complexity flagged rate within strong-engine positions: `{reluctance_summary['non_high_complexity']['flagged_rate_within_strong']}`.",
        f"- When flagged, humans still played the engine-best move only `{reluctance_summary['all']['human_played_anyway_rate_within_flagged']}` of the time.",
        "",
        "## Caveats",
        "",
        "- Stockfish actual-move ranks in the bundle are top-20 ranks, not full legal-move ranks.",
        "- Time-budget traces exist only for complex positions selected into the overnight sweep, so this section measures instability within the complex subset rather than complex vs non-complex.",
        "- These results validate phenomena using existing artifacts; they do not yet certify one final complexity definition.",
        "",
    ]
    return "\n".join(lines)


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument(
        "--bundle",
        type=Path,
        default=Path("outputs/sites/20260509_balanced_100_games/site/data/site_bundle.json"),
    )
    parser.add_argument(
        "--output-dir",
        type=Path,
        default=Path("research_agents/complexity_definition/results"),
    )
    args = parser.parse_args()

    bundle = load_bundle(args.bundle)
    rows = flatten_positions(bundle)
    rank_rows, rank_summary = compute_rank_tables(rows)
    time_rows, time_summary = compute_time_budget_tables(rows)
    reluctance_rows, reluctance_summary = compute_reluctance_tables(rows)

    bundle_summary = {
        "position_count": len(rows),
        "high_complexity_count": sum(row["high_complexity"] for row in rows),
        "non_high_complexity_count": sum(not row["high_complexity"] for row in rows),
        "time_budget_available_count": sum(row["time_budget_available"] for row in rows),
        "realizability_available_count": sum(row["realizability_available"] for row in rows),
    }

    summary_payload = {
        "bundle_path": str(args.bundle.resolve()),
        "bundle_summary": bundle_summary,
        "rank_summary": rank_summary,
        "time_budget_summary": time_summary,
        "engine_best_maia_reluctance_summary": reluctance_summary,
        "notes": [
            "Stockfish rank metrics are limited to the top-20 root analysis saved in the site bundle.",
            "Time-budget metrics are computed on positions with time-budget traces in the existing overnight complex-position sweep.",
            "This script only uses already-saved artifacts and does not rerun Maia or Stockfish.",
        ],
    }

    markdown = build_markdown(
        bundle_path=args.bundle.resolve(),
        bundle_summary=bundle_summary,
        rank_summary=rank_summary,
        time_summary=time_summary,
        reluctance_summary=reluctance_summary,
    )

    write_json(args.output_dir / "existing_artifact_validation.json", summary_payload)
    write_csv(args.output_dir / "rank_by_complexity.csv", rank_rows)
    write_csv(args.output_dir / "time_budget_by_complexity_bucket.csv", time_rows)
    write_csv(args.output_dir / "engine_best_maia_reluctance_by_slice.csv", reluctance_rows)
    (args.output_dir / "existing_artifact_validation.md").write_text(markdown + "\n", encoding="utf-8")


if __name__ == "__main__":
    main()
