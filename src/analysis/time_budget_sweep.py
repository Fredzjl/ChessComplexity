"""Stockfish time-budget sweep utilities for complex-position stability analysis."""

from __future__ import annotations

import csv
import json
import os
import statistics
import time
from concurrent.futures import ProcessPoolExecutor, as_completed
from dataclasses import asdict, dataclass
from pathlib import Path
from typing import Any

import chess
import yaml

from src.engines.stockfish_adapter import StockfishAdapter


def read_csv_rows(path: Path) -> list[dict[str, str]]:
    with path.open("r", encoding="utf-8", newline="") as handle:
        return list(csv.DictReader(handle))


def write_csv(path: Path, rows: list[dict[str, object]]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    if not rows:
        path.write_text("", encoding="utf-8")
        return

    with path.open("w", encoding="utf-8", newline="") as handle:
        writer = csv.DictWriter(handle, fieldnames=list(rows[0].keys()))
        writer.writeheader()
        writer.writerows(rows)


def write_json(path: Path, payload: object) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(payload, indent=2) + "\n", encoding="utf-8")


def write_jsonl(path: Path, rows: list[dict[str, object]]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open("w", encoding="utf-8") as handle:
        for row in rows:
            handle.write(json.dumps(row) + "\n")


def load_yaml(path: Path) -> dict[str, object]:
    return yaml.safe_load(path.read_text(encoding="utf-8"))


def sortable_score_cp(move: dict[str, object]) -> int:
    """Convert cp/mate payloads into one comparable signed integer."""
    cp = move.get("score_cp")
    if cp is not None:
        return int(cp)
    mate = move.get("score_mate")
    if mate is None:
        return 0
    sign = 1 if int(mate) > 0 else -1
    return sign * (100_000 - min(abs(int(mate)), 99_999))


def jaccard_overlap(left: list[str], right: list[str]) -> float:
    left_set = set(left)
    right_set = set(right)
    union = left_set | right_set
    if not union:
        return 1.0
    return len(left_set & right_set) / len(union)


def common_prefix_length(left: list[str], right: list[str]) -> int:
    count = 0
    for left_item, right_item in zip(left, right):
        if left_item != right_item:
            break
        count += 1
    return count


def summarize_numeric(values: list[float | int]) -> tuple[float | None, float | None, float | None]:
    if not values:
        return None, None, None
    return min(values), max(values), statistics.mean(values)


@dataclass(slots=True)
class SweepPosition:
    position_id: str
    game_id: str
    ply_index: int
    fullmove_number: int
    side_to_move: str
    fen: str
    white: str
    black: str
    white_elo: int
    black_elo: int
    image_path: str
    complexity_score: int
    actual_move_uci: str | None
    actual_move_san: str | None


def enrich_with_actual_moves(parsed_positions: list[dict[str, str]]) -> dict[str, dict[str, str | None]]:
    by_game: dict[str, list[dict[str, str]]] = {}
    for row in parsed_positions:
        by_game.setdefault(row["game_id"], []).append(row)
    for rows in by_game.values():
        rows.sort(key=lambda row: int(row["ply_index"]))

    lookup: dict[str, dict[str, str | None]] = {}
    for rows in by_game.values():
        for index, row in enumerate(rows):
            next_row = rows[index + 1] if index + 1 < len(rows) else None
            lookup[row["position_id"]] = {
                "actual_move_uci": next_row["lastmove_uci"] if next_row else None,
                "actual_move_san": next_row["lastmove_san"] if next_row else None,
            }
    return lookup


def _to_sweep_position(
    row: dict[str, str],
    actual_lookup: dict[str, dict[str, str | None]],
) -> SweepPosition:
    actual = actual_lookup.get(row["position_id"], {})
    return SweepPosition(
        position_id=row["position_id"],
        game_id=row["game_id"],
        ply_index=int(row["ply_index"]),
        fullmove_number=int(row["fullmove_number"]),
        side_to_move=row["side_to_move"],
        fen=row["fen"],
        white=row["white"],
        black=row["black"],
        white_elo=int(row["white_elo"]),
        black_elo=int(row["black_elo"]),
        image_path=row["image_path"],
        complexity_score=int(row["complexity_score"]),
        actual_move_uci=actual.get("actual_move_uci"),
        actual_move_san=actual.get("actual_move_san"),
    )


def choose_positions(
    *,
    score_rows: list[dict[str, str]],
    parsed_positions: list[dict[str, str]],
    game_id: str | None,
    max_positions: int,
    complex_only: bool,
    selection_mode: str = "single_game",
) -> tuple[str, str, list[SweepPosition]]:
    actual_lookup = enrich_with_actual_moves(parsed_positions)

    filtered_rows = [
        row
        for row in score_rows
        if row.get("inference_status") == "success"
        and (not complex_only or row.get("high_complexity") == "True")
    ]

    if selection_mode == "global_top_complexity":
        filtered_rows.sort(
            key=lambda row: (
                -int(row["complexity_score"]),
                row["game_id"],
                int(row["ply_index"]),
            )
        )
        chosen_rows = filtered_rows[:max_positions]
        if not chosen_rows:
            raise RuntimeError("No candidate positions found for global_top_complexity selection.")
        chosen = [_to_sweep_position(row, actual_lookup) for row in chosen_rows]
        return "GLOBAL_TOP_COMPLEXITY", f"Top {len(chosen)} high-complexity positions across all games", chosen

    if game_id is None:
        counts: dict[str, int] = {}
        for row in filtered_rows:
            counts[row["game_id"]] = counts.get(row["game_id"], 0) + 1
        if not counts:
            raise RuntimeError("No candidate positions available for the time-budget pilot.")
        game_id = max(counts.items(), key=lambda item: item[1])[0]

    game_rows = [row for row in filtered_rows if row["game_id"] == game_id]
    game_rows.sort(key=lambda row: int(row["ply_index"]))
    chosen_rows = game_rows[:max_positions]
    if not chosen_rows:
        raise RuntimeError(f"No candidate positions found for game_id={game_id}")

    chosen = [_to_sweep_position(row, actual_lookup) for row in chosen_rows]
    return game_id, f"{chosen[0].white} vs {chosen[0].black}" if chosen else "", chosen


def auto_worker_count(requested: str | int | None, position_count: int) -> int:
    if isinstance(requested, int):
        return max(1, min(requested, position_count))
    if isinstance(requested, str) and requested != "auto":
        return max(1, min(int(requested), position_count))
    cpu_count = os.cpu_count() or 4
    return max(1, min(position_count, cpu_count - 2 if cpu_count > 4 else cpu_count))


def analyse_one_position(payload: dict[str, object]) -> dict[str, object]:
    position = SweepPosition(**payload["position"])
    budgets_ms = [int(value) for value in payload["budgets_ms"]]
    binary_path = payload.get("binary_path")
    hash_mb = int(payload["hash_mb"])
    multipv = int(payload["multipv"])
    threads = int(payload["threads"])

    adapter = StockfishAdapter(
        binary_path=binary_path,
        threads=threads,
        hash_mb=hash_mb,
        movetime_ms=budgets_ms[0],
        multipv=multipv,
    )
    adapter.load()

    budget_rows: list[dict[str, object]] = []
    try:
        for budget_ms in budgets_ms:
            adapter.movetime_ms = budget_ms
            analysis = adapter.analyse(position.fen)
            moves = analysis["moves"]
            best_move = moves[0] if moves else {}
            actual_rank = None
            actual_score_text = None
            actual_score_cp = None
            actual_present = False
            if position.actual_move_uci:
                for move in moves:
                    if move["uci"] == position.actual_move_uci:
                        actual_rank = int(move["rank"])
                        actual_score_text = str(move["score_text"])
                        actual_score_cp = move["score_cp"]
                        actual_present = True
                        break

            budget_rows.append(
                {
                    "position_id": position.position_id,
                    "game_id": position.game_id,
                    "budget_ms": budget_ms,
                    "white": position.white,
                    "black": position.black,
                    "ply_index": position.ply_index,
                    "fullmove_number": position.fullmove_number,
                    "side_to_move": position.side_to_move,
                    "complexity_score": position.complexity_score,
                    "image_path": position.image_path,
                    "actual_move_uci": position.actual_move_uci,
                    "actual_move_san": position.actual_move_san,
                    "actual_move_rank": actual_rank,
                    "actual_move_rank_label": str(actual_rank) if actual_rank is not None else f">{multipv}",
                    "actual_move_in_topk": actual_present,
                    "actual_move_score_cp": actual_score_cp,
                    "actual_move_score_text": actual_score_text,
                    "best_move_uci": best_move.get("uci"),
                    "best_move_san": best_move.get("san"),
                    "best_move_score_cp": best_move.get("score_cp"),
                    "best_move_score_text": best_move.get("score_text"),
                    "best_move_depth": best_move.get("depth"),
                    "top_moves": moves,
                }
            )
    finally:
        adapter.close()

    stability = summarize_position_stability(position, budget_rows)
    return {
        "position": payload["position"],
        "budget_rows": budget_rows,
        "stability": stability,
    }


def summarize_position_stability(position: SweepPosition, budget_rows: list[dict[str, object]]) -> dict[str, object]:
    best_moves = [str(row["best_move_uci"]) for row in budget_rows if row.get("best_move_uci")]
    best_scores = [int(row["best_move_score_cp"]) for row in budget_rows if row.get("best_move_score_cp") is not None]
    best_move_switches = sum(
        1
        for previous, current in zip(best_moves, best_moves[1:])
        if previous != current
    )

    top3_overlaps: list[float] = []
    top5_overlaps: list[float] = []
    pv_prefix_lengths: list[int] = []
    actual_ranks = [int(row["actual_move_rank"]) for row in budget_rows if row.get("actual_move_rank") is not None]

    for left_row, right_row in zip(budget_rows, budget_rows[1:]):
        left_moves = left_row["top_moves"]
        right_moves = right_row["top_moves"]
        top3_overlaps.append(
            jaccard_overlap(
                [move["uci"] for move in left_moves[:3]],
                [move["uci"] for move in right_moves[:3]],
            )
        )
        top5_overlaps.append(
            jaccard_overlap(
                [move["uci"] for move in left_moves[:5]],
                [move["uci"] for move in right_moves[:5]],
            )
        )
        left_best = left_moves[0]["pv_uci"] if left_moves else []
        right_best = right_moves[0]["pv_uci"] if right_moves else []
        pv_prefix_lengths.append(common_prefix_length(left_best, right_best))

    score_min, score_max, score_mean = summarize_numeric(best_scores)
    top3_min, top3_max, top3_mean = summarize_numeric(top3_overlaps)
    top5_min, top5_max, top5_mean = summarize_numeric(top5_overlaps)
    pv_min, pv_max, pv_mean = summarize_numeric(pv_prefix_lengths)
    actual_rank_min, actual_rank_max, actual_rank_mean = summarize_numeric(actual_ranks)

    best_move_path = " | ".join(
        f"{row['budget_ms']}ms:{row['best_move_san'] or row['best_move_uci']}"
        for row in budget_rows
    )
    actual_rank_path = " | ".join(
        f"{row['budget_ms']}ms:{row['actual_move_rank_label']}"
        for row in budget_rows
    )

    return {
        "position_id": position.position_id,
        "game_id": position.game_id,
        "ply_index": position.ply_index,
        "fullmove_number": position.fullmove_number,
        "side_to_move": position.side_to_move,
        "white": position.white,
        "black": position.black,
        "white_elo": position.white_elo,
        "black_elo": position.black_elo,
        "complexity_score": position.complexity_score,
        "image_path": position.image_path,
        "actual_move_uci": position.actual_move_uci,
        "actual_move_san": position.actual_move_san,
        "budget_count": len(budget_rows),
        "best_move_path": best_move_path,
        "best_move_switch_count": best_move_switches,
        "unique_best_move_count": len(set(best_moves)),
        "best_score_min_cp": score_min,
        "best_score_max_cp": score_max,
        "best_score_mean_cp": round(score_mean, 4) if score_mean is not None else None,
        "best_score_range_cp": (score_max - score_min) if score_min is not None and score_max is not None else None,
        "adjacent_top3_overlap_min": round(top3_min, 4) if top3_min is not None else None,
        "adjacent_top3_overlap_mean": round(top3_mean, 4) if top3_mean is not None else None,
        "adjacent_top5_overlap_min": round(top5_min, 4) if top5_min is not None else None,
        "adjacent_top5_overlap_mean": round(top5_mean, 4) if top5_mean is not None else None,
        "best_pv_prefix_min_plies": pv_min,
        "best_pv_prefix_mean_plies": round(pv_mean, 4) if pv_mean is not None else None,
        "actual_move_present_budget_count": sum(1 for row in budget_rows if row["actual_move_in_topk"]),
        "actual_move_rank_min": actual_rank_min,
        "actual_move_rank_max": actual_rank_max,
        "actual_move_rank_mean": round(actual_rank_mean, 4) if actual_rank_mean is not None else None,
        "actual_move_rank_range": (
            actual_rank_max - actual_rank_min
            if actual_rank_min is not None and actual_rank_max is not None
            else None
        ),
        "actual_move_rank_path": actual_rank_path,
    }


def aggregate_summary(
    *,
    analysis_id: str,
    selected_game_id: str,
    positions: list[SweepPosition],
    stability_rows: list[dict[str, object]],
    budget_rows: list[dict[str, object]],
    budgets_ms: list[int],
    max_workers: int,
    stockfish_threads: int,
    multipv: int,
) -> dict[str, object]:
    switch_counts = [int(row["best_move_switch_count"]) for row in stability_rows]
    score_ranges = [
        int(row["best_score_range_cp"])
        for row in stability_rows
        if row["best_score_range_cp"] is not None
    ]
    actual_rank_ranges = [
        int(row["actual_move_rank_range"])
        for row in stability_rows
        if row["actual_move_rank_range"] is not None
    ]
    return {
        "analysis_id": analysis_id,
        "selected_game_id": selected_game_id,
        "game_label": f"{positions[0].white} vs {positions[0].black}" if positions else "",
        "selected_position_count": len(positions),
        "budget_count": len(budgets_ms),
        "budgets_ms": budgets_ms,
        "parallel": {
            "max_workers": max_workers,
            "stockfish_threads_per_worker": stockfish_threads,
            "multipv": multipv,
        },
        "position_ids": [position.position_id for position in positions],
        "best_move_switch_stats": {
            "min": min(switch_counts) if switch_counts else None,
            "max": max(switch_counts) if switch_counts else None,
            "mean": round(statistics.mean(switch_counts), 4) if switch_counts else None,
        },
        "best_score_range_stats": {
            "min": min(score_ranges) if score_ranges else None,
            "max": max(score_ranges) if score_ranges else None,
            "mean": round(statistics.mean(score_ranges), 4) if score_ranges else None,
        },
        "actual_move_rank_range_stats": {
            "min": min(actual_rank_ranges) if actual_rank_ranges else None,
            "max": max(actual_rank_ranges) if actual_rank_ranges else None,
            "mean": round(statistics.mean(actual_rank_ranges), 4) if actual_rank_ranges else None,
        },
        "root_analysis_row_count": len(budget_rows),
    }


def run_time_budget_sweep(
    *,
    score_rows: list[dict[str, str]],
    parsed_positions: list[dict[str, str]],
    analysis_config: dict[str, object],
) -> dict[str, object]:
    selection_cfg = analysis_config["selection"]
    stockfish_cfg = analysis_config["stockfish"]
    output_cfg = analysis_config["outputs"]

    selected_game_id, game_label, positions = choose_positions(
        score_rows=score_rows,
        parsed_positions=parsed_positions,
        game_id=selection_cfg.get("game_id"),
        max_positions=int(selection_cfg["max_positions"]),
        complex_only=bool(selection_cfg.get("complex_only", True)),
        selection_mode=str(selection_cfg.get("selection_mode", "single_game")),
    )

    budgets_ms = [int(value) for value in stockfish_cfg["time_budgets_ms"]]
    max_workers = auto_worker_count(stockfish_cfg.get("max_workers", "auto"), len(positions))
    threads_per_worker = int(stockfish_cfg.get("threads_per_worker", 1))
    hash_mb = int(stockfish_cfg.get("hash_mb", 128))
    multipv = int(stockfish_cfg.get("multipv", 10))
    binary_path = stockfish_cfg.get("binary_path")

    tasks = [
        {
            "position": asdict(position),
            "budgets_ms": budgets_ms,
            "binary_path": binary_path,
            "threads": threads_per_worker,
            "hash_mb": hash_mb,
            "multipv": multipv,
        }
        for position in positions
    ]

    budget_rows: list[dict[str, object]] = []
    stability_rows: list[dict[str, object]] = []
    start_time = time.time()
    total_tasks = len(tasks)
    completed = 0

    with ProcessPoolExecutor(max_workers=max_workers) as executor:
        future_map = {
            executor.submit(analyse_one_position, task): task["position"]["position_id"]
            for task in tasks
        }
        for future in as_completed(future_map):
            result = future.result()
            budget_rows.extend(result["budget_rows"])
            stability_rows.append(result["stability"])
            completed += 1
            if completed == total_tasks or completed % 25 == 0:
                elapsed = time.time() - start_time
                rate = completed / elapsed if elapsed > 0 else 0.0
                remaining = total_tasks - completed
                eta_seconds = remaining / rate if rate > 0 else None
                print(
                    json.dumps(
                        {
                            "time_budget_progress": {
                                "completed_positions": completed,
                                "total_positions": total_tasks,
                                "pct": round(completed / total_tasks, 4),
                                "elapsed_minutes": round(elapsed / 60, 2),
                                "eta_minutes": round(eta_seconds / 60, 2) if eta_seconds is not None else None,
                                "selected_scope": selected_game_id,
                            }
                        }
                    ),
                    flush=True,
                )

    budget_rows.sort(key=lambda row: (row["game_id"], int(row["ply_index"]), int(row["budget_ms"])))
    stability_rows.sort(key=lambda row: (row["game_id"], int(row["ply_index"])))

    summary = aggregate_summary(
        analysis_id=str(output_cfg["analysis_id"]),
        selected_game_id=selected_game_id,
        positions=positions,
        stability_rows=stability_rows,
        budget_rows=budget_rows,
        budgets_ms=budgets_ms,
        max_workers=max_workers,
        stockfish_threads=threads_per_worker,
        multipv=multipv,
    )
    summary["selection_mode"] = str(selection_cfg.get("selection_mode", "single_game"))
    summary["game_label"] = game_label
    selected_rows = [
        {
            "position_id": position.position_id,
            "game_id": position.game_id,
            "ply_index": position.ply_index,
            "fullmove_number": position.fullmove_number,
            "side_to_move": position.side_to_move,
            "white": position.white,
            "black": position.black,
            "white_elo": position.white_elo,
            "black_elo": position.black_elo,
            "complexity_score": position.complexity_score,
            "image_path": position.image_path,
            "actual_move_uci": position.actual_move_uci,
            "actual_move_san": position.actual_move_san,
            "fen": position.fen,
        }
        for position in positions
    ]
    return {
        "selected_rows": selected_rows,
        "budget_rows": budget_rows,
        "stability_rows": stability_rows,
        "summary": summary,
    }
