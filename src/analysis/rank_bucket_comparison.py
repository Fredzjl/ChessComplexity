"""Rank comparison analysis for actual human moves by Elo bucket."""

from __future__ import annotations

import csv
import json
import os
import statistics
from concurrent.futures import ProcessPoolExecutor, as_completed
from pathlib import Path
from typing import Any

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


def load_yaml(path: Path) -> dict[str, object]:
    return yaml.safe_load(path.read_text(encoding="utf-8"))


def load_raw_snapshots(path: Path) -> dict[str, dict[str, object]]:
    roots: dict[str, dict[str, object]] = {}
    with path.open("r", encoding="utf-8") as handle:
        for line in handle:
            snapshot = json.loads(line)
            if int(snapshot["depth"]) != 0:
                continue
            roots[str(snapshot["root_position_id"])] = snapshot
    return roots


def load_stockfish_cache(path: Path) -> dict[str, dict[str, object]]:
    if not path.exists():
        return {}
    return json.loads(path.read_text(encoding="utf-8"))


def side_to_move_elo(row: dict[str, str]) -> int:
    return int(row["white_elo"]) if row["side_to_move"] == "white" else int(row["black_elo"])


def elo_bucket_start(elo: int, width: int) -> int:
    return (elo // width) * width


def elo_bucket_label(start: int, width: int) -> str:
    return f"{start}-{start + width - 1}"


def actual_move_lookup(parsed_positions: list[dict[str, str]]) -> dict[str, dict[str, str | None]]:
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


def actual_move_maia_rank(root_snapshot: dict[str, object] | None, actual_uci: str | None) -> tuple[int | None, float | None]:
    if not root_snapshot or not actual_uci:
        return None, None
    for rank, (uci, probability) in enumerate(root_snapshot["move_probs"].items(), start=1):
        if uci == actual_uci:
            return rank, float(probability)
    return None, None


def actual_move_stockfish_rank(
    engine_analysis: dict[str, object] | None,
    actual_uci: str | None,
) -> tuple[int | None, str | None, int]:
    if not engine_analysis:
        return None, None, 0
    moves = engine_analysis.get("moves", [])
    topk_size = len(moves)
    if not actual_uci:
        return None, None, topk_size
    for move in moves:
        if move["uci"] == actual_uci:
            return int(move["rank"]), str(move["score_text"]), topk_size
    return None, None, topk_size


def analyze_stockfish_batch(task: dict[str, object]) -> dict[str, dict[str, object]]:
    adapter = StockfishAdapter(
        binary_path=task.get("binary_path"),
        threads=int(task["threads_per_worker"]),
        hash_mb=int(task["hash_mb"]),
        movetime_ms=int(task["movetime_ms"]),
        multipv=int(task["multipv"]),
    )
    adapter.load()
    results: dict[str, dict[str, object]] = {}
    try:
        for row in task["rows"]:
            results[row["position_id"]] = adapter.analyse(row["fen"])
    finally:
        adapter.close()
    return results


def chunk_rows(rows: list[dict[str, str]], chunk_count: int) -> list[list[dict[str, str]]]:
    if chunk_count <= 1:
        return [rows]
    chunks: list[list[dict[str, str]]] = [[] for _ in range(chunk_count)]
    for index, row in enumerate(rows):
        chunks[index % chunk_count].append(row)
    return [chunk for chunk in chunks if chunk]


def auto_worker_count(requested: str | int | None, position_count: int) -> int:
    if isinstance(requested, int):
        return max(1, min(requested, position_count))
    if isinstance(requested, str) and requested != "auto":
        return max(1, min(int(requested), position_count))
    cpu_count = os.cpu_count() or 4
    candidate = cpu_count - 2 if cpu_count > 4 else cpu_count
    return max(1, min(position_count, candidate))


def build_stockfish_cache(
    *,
    position_rows: list[dict[str, str]],
    cache_path: Path,
    binary_path: str | None,
    movetime_ms: int,
    multipv: int,
    threads_per_worker: int,
    max_workers: int,
    hash_mb: int,
    refresh_cache: bool,
) -> dict[str, dict[str, object]]:
    cache = {} if refresh_cache else load_stockfish_cache(cache_path)
    missing_rows = [row for row in position_rows if row["position_id"] not in cache]
    if not missing_rows:
        return cache

    tasks = [
        {
            "rows": chunk,
            "binary_path": binary_path,
            "movetime_ms": movetime_ms,
            "multipv": multipv,
            "threads_per_worker": threads_per_worker,
            "hash_mb": hash_mb,
        }
        for chunk in chunk_rows(missing_rows, max_workers)
    ]

    with ProcessPoolExecutor(max_workers=max_workers) as executor:
        futures = [executor.submit(analyze_stockfish_batch, task) for task in tasks]
        for future in as_completed(futures):
            cache.update(future.result())

    write_json(cache_path, cache)
    return cache


def scoped_position_rows(
    *,
    score_rows: list[dict[str, str]],
    actual_lookup: dict[str, dict[str, str | None]],
    min_player_elo: int,
) -> list[dict[str, object]]:
    rows: list[dict[str, object]] = []
    for row in score_rows:
        actual = actual_lookup.get(row["position_id"], {})
        actual_uci = actual.get("actual_move_uci")
        actual_san = actual.get("actual_move_san")
        player_elo = side_to_move_elo(row)
        if player_elo < min_player_elo or not actual_uci:
            continue
        rows.append(
            {
                "position_id": row["position_id"],
                "game_id": row["game_id"],
                "ply_index": int(row["ply_index"]),
                "fullmove_number": int(row["fullmove_number"]),
                "side_to_move": row["side_to_move"],
                "player_elo": player_elo,
                "white_elo": int(row["white_elo"]),
                "black_elo": int(row["black_elo"]),
                "white": row["white"],
                "black": row["black"],
                "fen": row["fen"],
                "actual_move_uci": actual_uci,
                "actual_move_san": actual_san,
                "high_complexity": row["high_complexity"] == "True",
                "complexity_score": int(row["complexity_score"]) if row["complexity_score"] else None,
                "image_path": row["image_path"],
                "inference_status": row["inference_status"],
            }
        )
    return rows


def build_position_level_rows(
    *,
    scoped_rows: list[dict[str, object]],
    root_snapshots: dict[str, dict[str, object]],
    stockfish_cache: dict[str, dict[str, object]],
    elo_bucket_width: int,
) -> list[dict[str, object]]:
    position_rows: list[dict[str, object]] = []
    for row in scoped_rows:
        position_id = str(row["position_id"])
        bucket_start = elo_bucket_start(int(row["player_elo"]), elo_bucket_width)
        bucket_label = elo_bucket_label(bucket_start, elo_bucket_width)
        root_snapshot = root_snapshots.get(position_id)
        engine_analysis = stockfish_cache.get(position_id)

        maia_rank, maia_probability = actual_move_maia_rank(root_snapshot, str(row["actual_move_uci"]))
        stockfish_rank, stockfish_score_text, stockfish_topk = actual_move_stockfish_rank(
            engine_analysis,
            str(row["actual_move_uci"]),
        )
        clipped_rank = stockfish_rank if stockfish_rank is not None else (stockfish_topk + 1 if stockfish_topk else None)

        position_rows.append(
            {
                **row,
                "elo_bucket_start": bucket_start,
                "elo_bucket_label": bucket_label,
                "maia_rank": maia_rank,
                "maia_probability": maia_probability,
                "maia_covered": maia_rank is not None,
                "maia_hit_at_1": maia_rank is not None and maia_rank <= 1,
                "maia_hit_at_3": maia_rank is not None and maia_rank <= 3,
                "maia_hit_at_5": maia_rank is not None and maia_rank <= 5,
                "stockfish_rank_found": stockfish_rank,
                "stockfish_rank_clipped": clipped_rank,
                "stockfish_topk": stockfish_topk,
                "stockfish_score_text": stockfish_score_text,
                "stockfish_covered": stockfish_rank is not None,
                "stockfish_hit_at_1": clipped_rank is not None and clipped_rank <= 1,
                "stockfish_hit_at_3": clipped_rank is not None and clipped_rank <= 3,
                "stockfish_hit_at_5": clipped_rank is not None and clipped_rank <= 5,
            }
        )
    position_rows.sort(key=lambda item: (item["elo_bucket_start"], item["game_id"], item["ply_index"]))
    return position_rows


def summarize_rank_values(values: list[int]) -> tuple[float | None, float | None]:
    if not values:
        return None, None
    return round(statistics.mean(values), 4), float(statistics.median(values))


def bucket_row_for_model(
    *,
    model: str,
    scope: str,
    bucket_label: str,
    bucket_start: int,
    rows: list[dict[str, object]],
) -> dict[str, object]:
    position_count = len(rows)
    if model == "maia":
        exact_ranks = [int(row["maia_rank"]) for row in rows if row["maia_rank"] is not None]
        mean_rank, median_rank = summarize_rank_values(exact_ranks)
        coverage = len(exact_ranks) / position_count if position_count else None
        return {
            "model": model,
            "scope": scope,
            "elo_bucket_start": bucket_start,
            "elo_bucket_label": bucket_label,
            "position_count": position_count,
            "covered_positions": len(exact_ranks),
            "coverage": round(coverage, 4) if coverage is not None else None,
            "mean_rank": mean_rank,
            "median_rank": median_rank,
            "mean_rank_found_only": mean_rank,
            "median_rank_found_only": median_rank,
            "mean_rank_topk_clipped": mean_rank,
            "median_rank_topk_clipped": median_rank,
            "hit_at_1": round(sum(1 for row in rows if row["maia_hit_at_1"]) / position_count, 4) if position_count else None,
            "hit_at_3": round(sum(1 for row in rows if row["maia_hit_at_3"]) / position_count, 4) if position_count else None,
            "hit_at_5": round(sum(1 for row in rows if row["maia_hit_at_5"]) / position_count, 4) if position_count else None,
            "topk_size": None,
        }

    found_ranks = [int(row["stockfish_rank_found"]) for row in rows if row["stockfish_rank_found"] is not None]
    clipped_ranks = [int(row["stockfish_rank_clipped"]) for row in rows if row["stockfish_rank_clipped"] is not None]
    mean_found, median_found = summarize_rank_values(found_ranks)
    mean_clipped, median_clipped = summarize_rank_values(clipped_ranks)
    coverage = len(found_ranks) / position_count if position_count else None
    topk_size = max((int(row["stockfish_topk"]) for row in rows if row["stockfish_topk"]), default=0)
    return {
        "model": model,
        "scope": scope,
        "elo_bucket_start": bucket_start,
        "elo_bucket_label": bucket_label,
        "position_count": position_count,
        "covered_positions": len(found_ranks),
        "coverage": round(coverage, 4) if coverage is not None else None,
        "mean_rank": mean_clipped,
        "median_rank": median_clipped,
        "mean_rank_found_only": mean_found,
        "median_rank_found_only": median_found,
        "mean_rank_topk_clipped": mean_clipped,
        "median_rank_topk_clipped": median_clipped,
        "hit_at_1": round(sum(1 for row in rows if row["stockfish_hit_at_1"]) / position_count, 4) if position_count else None,
        "hit_at_3": round(sum(1 for row in rows if row["stockfish_hit_at_3"]) / position_count, 4) if position_count else None,
        "hit_at_5": round(sum(1 for row in rows if row["stockfish_hit_at_5"]) / position_count, 4) if position_count else None,
        "topk_size": topk_size,
    }


def build_bucket_summary_rows(
    *,
    position_rows: list[dict[str, object]],
) -> list[dict[str, object]]:
    grouped: dict[tuple[str, str, int, str], list[dict[str, object]]] = {}
    for row in position_rows:
        scopes = ["all_eligible", "high_complexity"] if row["high_complexity"] else ["all_eligible"]
        for scope in scopes:
            for model in ["maia", "stockfish"]:
                key = (model, scope, int(row["elo_bucket_start"]), str(row["elo_bucket_label"]))
                grouped.setdefault(key, []).append(row)

    summary_rows: list[dict[str, object]] = []
    for (model, scope, bucket_start, bucket_label), rows in sorted(grouped.items()):
        summary_rows.append(
            bucket_row_for_model(
                model=model,
                scope=scope,
                bucket_label=bucket_label,
                bucket_start=bucket_start,
                rows=rows,
            )
        )
    return summary_rows


def overall_scope_summary(
    *,
    bucket_rows: list[dict[str, object]],
    scope: str,
    model: str,
) -> dict[str, object]:
    rows = [
        row
        for row in bucket_rows
        if row["scope"] == scope and row["model"] == model
    ]
    total_positions = sum(int(row["position_count"]) for row in rows)
    if total_positions == 0:
        return {}

    def weighted(metric: str) -> float | None:
        pairs = [
            (float(row[metric]), int(row["position_count"]))
            for row in rows
            if row.get(metric) is not None
        ]
        if not pairs:
            return None
        return round(sum(value * weight for value, weight in pairs) / total_positions, 4)

    return {
        "position_count": total_positions,
        "covered_positions": sum(int(row["covered_positions"]) for row in rows),
        "coverage": weighted("coverage"),
        "mean_rank": weighted("mean_rank"),
        "mean_rank_found_only": weighted("mean_rank_found_only"),
        "mean_rank_topk_clipped": weighted("mean_rank_topk_clipped"),
        "hit_at_1": weighted("hit_at_1"),
        "hit_at_3": weighted("hit_at_3"),
        "hit_at_5": weighted("hit_at_5"),
        "topk_size": max((int(row["topk_size"]) for row in rows if row["topk_size"] is not None), default=0) or None,
    }


def build_summary_payload(
    *,
    config: dict[str, object],
    bucket_rows: list[dict[str, object]],
    position_rows: list[dict[str, object]],
) -> dict[str, object]:
    population_cfg = config["population"]
    stockfish_cfg = config["models"]["stockfish"]
    return {
        "experiment_name": config["experiment_name"],
        "min_player_elo": int(population_cfg["min_player_elo"]),
        "elo_bucket_width": int(population_cfg["elo_bucket_width"]),
        "scoped_position_count": len(position_rows),
        "slices": {
            "all_eligible": {
                "label": "All eligible positions",
                "maia": overall_scope_summary(bucket_rows=bucket_rows, scope="all_eligible", model="maia"),
                "stockfish": overall_scope_summary(bucket_rows=bucket_rows, scope="all_eligible", model="stockfish"),
            },
            "high_complexity": {
                "label": "High-complexity positions",
                "maia": overall_scope_summary(bucket_rows=bucket_rows, scope="high_complexity", model="maia"),
                "stockfish": overall_scope_summary(bucket_rows=bucket_rows, scope="high_complexity", model="stockfish"),
            },
        },
        "stockfish": {
            "movetime_ms": int(stockfish_cfg["movetime_ms"]),
            "multipv": int(stockfish_cfg["multipv"]),
        },
    }

