#!/usr/bin/env python3
"""Build a static review website from the current experiment outputs."""

from __future__ import annotations

import argparse
import csv
import json
import statistics
import shutil
import sys
from collections import defaultdict
from datetime import datetime, timezone
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parents[2]
if str(REPO_ROOT) not in sys.path:
    sys.path.insert(0, str(REPO_ROOT))

from src.engines.stockfish_adapter import StockfishAdapter


def read_csv_rows(path: Path) -> list[dict[str, str]]:
    with path.open("r", encoding="utf-8", newline="") as handle:
        return list(csv.DictReader(handle))


def read_json(path: Path) -> dict[str, object]:
    return json.loads(path.read_text(encoding="utf-8"))


def read_optional_json(path: Path | None) -> dict[str, object] | None:
    if path is None or not path.exists():
        return None
    return read_json(path)


def load_raw_snapshots(path: Path) -> dict[str, list[dict[str, object]]]:
    grouped: dict[str, list[dict[str, object]]] = defaultdict(list)
    with path.open("r", encoding="utf-8") as handle:
        for line in handle:
            snapshot = json.loads(line)
            grouped[str(snapshot["root_position_id"])].append(snapshot)
    return grouped


def load_optional_csv_rows(path: Path | None) -> list[dict[str, str]]:
    if path is None or not path.exists():
        return []
    return read_csv_rows(path)


def parse_bool(value: str | bool | None) -> bool | None:
    if isinstance(value, bool):
        return value
    if value is None or value == "":
        return None
    return str(value).lower() == "true"


def parse_int(value: str | int | None) -> int | None:
    if isinstance(value, int):
        return value
    if value is None or value == "":
        return None
    return int(value)


def parse_float(value: str | float | None) -> float | None:
    if isinstance(value, float):
        return value
    if value is None or value == "":
        return None
    return float(value)


def realizability_position_lookup(rows: list[dict[str, str]]) -> dict[str, dict[str, object]]:
    lookup: dict[str, dict[str, object]] = {}
    for row in rows:
        lookup[row["position_id"]] = {
            "actual_candidate_available": parse_bool(row["actual_candidate_available"]),
            "actual_realizability_score_v0": parse_float(row["actual_realizability_score_v0"]),
            "actual_maia_probability": parse_float(row["actual_maia_probability"]),
            "actual_maia_rank": parse_int(row["actual_maia_rank"]),
            "engine_best_uci": row["engine_best_uci"] or None,
            "engine_best_san": row["engine_best_san"] or None,
            "engine_best_realizability_score_v0": parse_float(row["engine_best_realizability_score_v0"]),
            "engine_best_maia_probability": parse_float(row["engine_best_maia_probability"]),
            "engine_best_maia_rank": parse_int(row["engine_best_maia_rank"]),
            "top_realizability_uci": row["top_realizability_uci"] or None,
            "top_realizability_san": row["top_realizability_san"] or None,
            "top_realizability_score_v0": parse_float(row["top_realizability_score_v0"]),
            "actual_minus_engine_best_realizability": parse_float(row["actual_minus_engine_best_realizability"]),
            "actual_matches_engine_best": parse_bool(row["actual_matches_engine_best"]),
            "actual_matches_top_realizability": parse_bool(row["actual_matches_top_realizability"]),
            "actual_beats_engine_best": parse_bool(row["actual_beats_engine_best"]),
            "candidate_count": parse_int(row["candidate_count"]),
        }
    return lookup


def realizability_candidate_lookup(rows: list[dict[str, str]]) -> dict[str, list[dict[str, object]]]:
    grouped: dict[str, list[dict[str, object]]] = defaultdict(list)
    for row in rows:
        grouped[row["position_id"]].append(
            {
                "candidate_uci": row["candidate_uci"],
                "candidate_san": row["candidate_san"],
                "candidate_role": row["candidate_role"],
                "forced_include_actual": parse_bool(row["forced_include_actual"]),
                "is_actual_move": parse_bool(row["is_actual_move"]),
                "is_engine_best": parse_bool(row["is_engine_best"]),
                "root_rank": parse_int(row["root_rank"]),
                "root_value_cp": parse_int(row["root_value_cp"]),
                "distance_from_best_cp": parse_int(row["distance_from_best_cp"]),
                "viable_threshold_cp": parse_int(row["viable_threshold_cp"]),
                "acceptable_width_player_d1": parse_float(row["acceptable_width_player_d1"]),
                "acceptable_width_player_mean": parse_float(row["acceptable_width_player_mean"]),
                "acceptable_width_player_min": parse_int(row["acceptable_width_player_min"]),
                "acceptable_width_d3": parse_float(row["acceptable_width_d3"]),
                "survival_rate_after_opponent": parse_float(row["survival_rate_after_opponent"]),
                "opponent_refutation_density": parse_float(row["opponent_refutation_density"]),
                "depth4_survival_rate": parse_float(row["depth4_survival_rate"]),
                "unique_burden_plies": parse_int(row["unique_burden_plies"]),
                "longest_narrow_streak": parse_int(row["longest_narrow_streak"]),
                "deviation_penalty_cp_mean": parse_float(row["deviation_penalty_cp_mean"]),
                "deviation_penalty_cp_max": parse_int(row["deviation_penalty_cp_max"]),
                "mean_margin_to_viable_cp": parse_float(row["mean_margin_to_viable_cp"]),
                "conversion_horizon_plies": parse_int(row["conversion_horizon_plies"]),
                "conversion_success_within_horizon": parse_bool(row["conversion_success_within_horizon"]),
                "maia_rank": parse_int(row["maia_rank"]),
                "maia_probability": parse_float(row["maia_probability"]),
                "realizability_score_v0": parse_float(row["realizability_score_v0"]),
            }
        )
    for candidates in grouped.values():
        candidates.sort(
            key=lambda item: (
                -(item["realizability_score_v0"] or 0),
                0 if item["is_actual_move"] else 1,
                item["candidate_uci"],
            )
        )
    return grouped


def time_budget_position_lookup(rows: list[dict[str, str]]) -> dict[str, dict[str, object]]:
    lookup: dict[str, dict[str, object]] = {}
    for row in rows:
        lookup[row["position_id"]] = {
            "budget_count": parse_int(row["budget_count"]),
            "best_move_path": row["best_move_path"],
            "best_move_switch_count": parse_int(row["best_move_switch_count"]),
            "unique_best_move_count": parse_int(row["unique_best_move_count"]),
            "best_score_min_cp": parse_int(row["best_score_min_cp"]),
            "best_score_max_cp": parse_int(row["best_score_max_cp"]),
            "best_score_mean_cp": parse_float(row["best_score_mean_cp"]),
            "best_score_range_cp": parse_int(row["best_score_range_cp"]),
            "adjacent_top3_overlap_min": parse_float(row["adjacent_top3_overlap_min"]),
            "adjacent_top3_overlap_mean": parse_float(row["adjacent_top3_overlap_mean"]),
            "adjacent_top5_overlap_min": parse_float(row["adjacent_top5_overlap_min"]),
            "adjacent_top5_overlap_mean": parse_float(row["adjacent_top5_overlap_mean"]),
            "best_pv_prefix_min_plies": parse_int(row["best_pv_prefix_min_plies"]),
            "best_pv_prefix_mean_plies": parse_float(row["best_pv_prefix_mean_plies"]),
            "actual_move_present_budget_count": parse_int(row["actual_move_present_budget_count"]),
            "actual_move_rank_min": parse_int(row["actual_move_rank_min"]),
            "actual_move_rank_max": parse_int(row["actual_move_rank_max"]),
            "actual_move_rank_mean": parse_float(row["actual_move_rank_mean"]),
            "actual_move_rank_range": parse_int(row["actual_move_rank_range"]),
            "actual_move_rank_path": row["actual_move_rank_path"],
        }
    return lookup


def time_budget_rows_lookup(rows: list[dict[str, str]]) -> dict[str, list[dict[str, object]]]:
    grouped: dict[str, list[dict[str, object]]] = defaultdict(list)
    for row in rows:
        grouped[row["position_id"]].append(
            {
                "budget_ms": parse_int(row["budget_ms"]),
                "best_move_uci": row["best_move_uci"],
                "best_move_san": row["best_move_san"],
                "best_move_score_cp": parse_int(row["best_move_score_cp"]),
                "best_move_score_text": row["best_move_score_text"],
                "best_move_depth": parse_int(row["best_move_depth"]),
                "actual_move_uci": row["actual_move_uci"],
                "actual_move_san": row["actual_move_san"],
                "actual_move_rank": parse_int(row["actual_move_rank"]),
                "actual_move_rank_label": row["actual_move_rank_label"],
                "actual_move_in_topk": parse_bool(row["actual_move_in_topk"]),
                "actual_move_score_cp": parse_int(row["actual_move_score_cp"]),
                "actual_move_score_text": row["actual_move_score_text"],
            }
        )
    for budget_rows in grouped.values():
        budget_rows.sort(key=lambda row: row["budget_ms"] or 0)
    return grouped


def positions_by_game(rows: list[dict[str, str]]) -> dict[str, list[dict[str, str]]]:
    grouped: dict[str, list[dict[str, str]]] = defaultdict(list)
    for row in rows:
        grouped[row["game_id"]].append(row)
    for game_id in grouped:
        grouped[game_id].sort(key=lambda row: int(row["ply_index"]))
    return grouped


def move_text(rows: list[dict[str, str]]) -> str:
    parts: list[str] = []
    for row in rows:
        ply_index = int(row["ply_index"])
        fullmove = (ply_index + 1) // 2
        san = row["lastmove_san"]
        if ply_index % 2 == 1:
            parts.append(f"{fullmove}. {san}")
        else:
            parts.append(san)
    return " ".join(parts)


def position_label(row: dict[str, str]) -> str:
    side = "W" if row["side_to_move"] == "white" else "B"
    return f"{row['fullmove_number']}{side}"


def actual_move_payload(
    game_rows: list[dict[str, str]],
    index: int,
) -> dict[str, object] | None:
    if index + 1 >= len(game_rows):
        return None
    next_row = game_rows[index + 1]
    return {
        "position_id_after_move": next_row["position_id"],
        "uci": next_row["lastmove_uci"],
        "san": next_row["lastmove_san"],
        "side": "black" if next_row["side_to_move"] == "white" else "white",
        "fullmove_number": int(next_row["fullmove_number"]),
    }


def continuation_payload(
    game_rows: list[dict[str, str]],
    index: int,
    *,
    max_plies: int = 6,
) -> list[dict[str, object]]:
    continuation: list[dict[str, object]] = []
    for row in game_rows[index + 1 : index + 1 + max_plies]:
        continuation.append(
            {
                "position_id": row["position_id"],
                "uci": row["lastmove_uci"],
                "san": row["lastmove_san"],
                "side_to_move_after": row["side_to_move"],
                "fullmove_number": int(row["fullmove_number"]),
            }
        )
    return continuation


def top_moves_from_snapshot(snapshot: dict[str, object], *, top_k: int = 10) -> list[dict[str, object]]:
    top_moves: list[dict[str, object]] = []
    qualifying = set(snapshot["qualifying_moves"])
    move_probs = list(snapshot["move_probs"].items())[:top_k]
    for rank, (uci, probability) in enumerate(move_probs, start=1):
        top_moves.append(
            {
                "rank": rank,
                "uci": uci,
                "probability": probability,
                "qualifies": uci in qualifying,
            }
        )
    return top_moves


def snapshot_nodes_by_depth(snapshot_rows: list[dict[str, object]]) -> dict[str, list[dict[str, object]]]:
    grouped: dict[str, list[dict[str, object]]] = {"0": [], "1": [], "2": []}
    for snapshot in snapshot_rows:
        depth_key = str(snapshot["depth"])
        if depth_key not in grouped:
            continue
        grouped[depth_key].append(
            {
                "node_id": snapshot["node_id"],
                "parent_node_id": snapshot["parent_node_id"],
                "depth": snapshot["depth"],
                "path_uci": snapshot["path_uci"],
                "path_probability": snapshot["path_probability"],
                "qualifying_move_count": snapshot["qualifying_move_count"],
                "qualifying_moves": [
                    {
                        "uci": move,
                        "probability": snapshot["qualifying_probabilities"][move],
                    }
                    for move in snapshot["qualifying_moves"]
                ],
                "top_moves": top_moves_from_snapshot(snapshot, top_k=5),
                "win_prob": snapshot["win_prob"],
            }
        )
    return grouped


def write_json(path: Path, payload: object) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(payload, indent=2) + "\n", encoding="utf-8")


def copy_template(template_dir: Path, site_dir: Path) -> None:
    site_dir.mkdir(parents=True, exist_ok=True)
    for template_path in template_dir.iterdir():
        if template_path.is_file():
            shutil.copy2(template_path, site_dir / template_path.name)


def ensure_board_assets(source_dir: Path, assets_dir: Path) -> None:
    """Expose rendered board PNGs inside the site without per-image copying."""
    if assets_dir.exists() or assets_dir.is_symlink():
        if assets_dir.is_symlink() or assets_dir.is_file():
            assets_dir.unlink()
        else:
            shutil.rmtree(assets_dir)
    assets_dir.parent.mkdir(parents=True, exist_ok=True)
    try:
        assets_dir.symlink_to(source_dir.resolve(), target_is_directory=True)
    except OSError:
        shutil.copytree(source_dir, assets_dir)


def copy_board_assets_for_bundle(
    bundle: dict[str, object],
    *,
    source_dir: Path,
    assets_dir: Path,
) -> None:
    """Copy only the referenced board PNGs into the publishable site."""
    if assets_dir.exists() or assets_dir.is_symlink():
        if assets_dir.is_symlink() or assets_dir.is_file():
            assets_dir.unlink()
        else:
            shutil.rmtree(assets_dir)
    assets_dir.mkdir(parents=True, exist_ok=True)

    referenced_names: set[str] = set()
    for game in bundle.get("games", []):
        for position in game.get("positions", []):
            board_image = position.get("board_image")
            if not board_image:
                continue
            referenced_names.add(Path(str(board_image)).name)

    for name in sorted(referenced_names):
        source_path = source_dir / name
        if not source_path.exists():
            raise FileNotFoundError(f"Missing board asset referenced by site: {source_path}")
        shutil.copy2(source_path, assets_dir / name)


def write_split_site_data(site_dir: Path, bundle: dict[str, object]) -> dict[str, object]:
    """Write a publishable, chunked site payload."""
    data_dir = site_dir / "data"
    games_dir = data_dir / "games"
    data_dir.mkdir(parents=True, exist_ok=True)
    games_dir.mkdir(parents=True, exist_ok=True)

    games_manifest: list[dict[str, object]] = []
    total_positions = 0
    for game in bundle["games"]:
        total_positions += len(game["positions"])
        game_payload = dict(game)
        game_payload["data_path"] = f"data/games/{game['game_id']}.json"
        write_json(games_dir / f"{game['game_id']}.json", game_payload)

        manifest_entry = {key: value for key, value in game.items() if key != "positions"}
        manifest_entry["position_count"] = len(game["positions"])
        manifest_entry["data_path"] = game_payload["data_path"]
        games_manifest.append(manifest_entry)

    write_json(
        data_dir / "summary.json",
        {
            "generated_at": bundle["generated_at"],
            "summary": bundle["summary"],
        },
    )
    write_json(data_dir / "experiments.json", bundle.get("experiments", {}))
    write_json(
        data_dir / "games_manifest.json",
        {
            "generated_at": bundle["generated_at"],
            "games": games_manifest,
        },
    )
    (site_dir / ".nojekyll").write_text("", encoding="utf-8")

    return {
        "mode": "split_games",
        "game_count": len(games_manifest),
        "position_count": total_positions,
        "files": {
            "summary": str(data_dir / "summary.json"),
            "experiments": str(data_dir / "experiments.json"),
            "games_manifest": str(data_dir / "games_manifest.json"),
            "games_dir": str(games_dir),
        },
    }


def load_stockfish_cache(path: Path) -> dict[str, dict[str, object]]:
    if not path.exists():
        return {}
    return json.loads(path.read_text(encoding="utf-8"))


def build_stockfish_analysis(
    position_rows: list[dict[str, str]],
    *,
    cache_path: Path,
    movetime_ms: int,
    multipv: int,
    refresh_cache: bool = False,
) -> dict[str, dict[str, object]]:
    cache = {} if refresh_cache else load_stockfish_cache(cache_path)
    adapter = StockfishAdapter(movetime_ms=movetime_ms, multipv=multipv)
    adapter.load()

    try:
        for index, row in enumerate(position_rows, start=1):
            position_id = row["position_id"]
            if position_id in cache:
                continue
            cache[position_id] = adapter.analyse(row["fen"])
            if index % 25 == 0:
                print(
                    json.dumps(
                        {
                            "stockfish_progress": index,
                            "total_positions": len(position_rows),
                            "cached_positions": len(cache),
                        }
                    )
                )
    finally:
        adapter.close()

    write_json(cache_path, cache)
    return cache


def actual_move_model_rank(root_snapshot: dict[str, object] | None, actual_uci: str | None) -> tuple[int | None, float | None, bool | None]:
    if not root_snapshot or not actual_uci:
        return None, None, None
    move_probs = list(root_snapshot["move_probs"].items())
    for rank, (uci, probability) in enumerate(move_probs, start=1):
        if uci == actual_uci:
            return rank, probability, uci in set(root_snapshot["qualifying_moves"])
    return None, None, False


def actual_move_engine_rank(engine_analysis: dict[str, object] | None, actual_uci: str | None) -> tuple[int | None, str | None]:
    if not engine_analysis or not actual_uci:
        return None, None
    for move in engine_analysis.get("moves", []):
        if move["uci"] == actual_uci:
            return int(move["rank"]), str(move["score_text"])
    return None, None


def root_move_rank_probability(
    root_snapshot: dict[str, object] | None,
    move_uci: str | None,
) -> tuple[int | None, float | None]:
    """Return one move's exact Maia rank and probability from the full root policy."""
    if not root_snapshot or not move_uci:
        return None, None
    for rank, (uci, probability) in enumerate(root_snapshot["move_probs"].items(), start=1):
        if uci == move_uci:
            return rank, float(probability)
    return None, None


def maia_engine_conflict_payload(
    *,
    root_snapshot: dict[str, object] | None,
    engine_analysis: dict[str, object] | None,
    actual_move: dict[str, object] | None,
    gap_threshold_cp: int,
) -> dict[str, object]:
    """Describe Maia-high moves that Stockfish values much lower than its best move."""
    if not root_snapshot or not engine_analysis or not engine_analysis.get("moves"):
        return {
            "flagged": False,
            "move_count": 0,
            "moves": [],
            "shallow_missing_count": 0,
            "shallow_missing_moves": [],
            "gap_threshold_cp": gap_threshold_cp,
        }

    best_move = engine_analysis["moves"][0]
    best_cp = best_move.get("score_cp")
    if best_cp is None:
        return {
            "flagged": False,
            "move_count": 0,
            "moves": [],
            "shallow_missing_count": 0,
            "shallow_missing_moves": [],
            "gap_threshold_cp": gap_threshold_cp,
        }

    engine_map = {move["uci"]: move for move in engine_analysis["moves"]}
    actual_uci = actual_move["uci"] if actual_move else None
    conflict_moves: list[dict[str, object]] = []
    shallow_missing: list[dict[str, object]] = []
    for rank, (uci, probability) in enumerate(root_snapshot["move_probs"].items(), start=1):
        if probability < 0.10:
            continue
        engine_move = engine_map.get(uci)
        if engine_move is None:
            shallow_missing.append(
                {
                    "uci": uci,
                    "probability": float(probability),
                    "maia_rank": rank,
                    "is_actual_move": uci == actual_uci,
                }
            )
            continue
        move_cp = engine_move.get("score_cp")
        if move_cp is None:
            continue
        gap_cp = best_cp - move_cp
        if gap_cp < gap_threshold_cp:
            continue
        conflict_moves.append(
            {
                "uci": uci,
                "san": engine_move.get("san", uci),
                "probability": float(probability),
                "maia_rank": rank,
                "engine_rank": int(engine_move["rank"]),
                "engine_score_text": str(engine_move["score_text"]),
                "gap_cp": int(gap_cp),
                "is_actual_move": uci == actual_uci,
            }
        )

    return {
        "flagged": bool(conflict_moves),
        "move_count": len(conflict_moves),
        "moves": conflict_moves,
        "shallow_missing_count": len(shallow_missing),
        "shallow_missing_moves": shallow_missing[:10],
        "gap_threshold_cp": gap_threshold_cp,
    }


def engine_best_reluctant_payload(
    *,
    root_snapshot: dict[str, object] | None,
    engine_analysis: dict[str, object] | None,
    actual_move: dict[str, object] | None,
    strong_threshold_cp: int,
    reluctant_probability: float,
) -> dict[str, object]:
    """Describe positions where Stockfish loves one move that Maia discounts."""
    if not root_snapshot or not engine_analysis or not engine_analysis.get("moves"):
        return {
            "flagged": False,
            "strong_threshold_cp": strong_threshold_cp,
            "reluctant_probability": reluctant_probability,
            "engine_best": None,
        }

    best_move = engine_analysis["moves"][0]
    best_cp = best_move.get("score_cp")
    if best_cp is None:
        return {
            "flagged": False,
            "strong_threshold_cp": strong_threshold_cp,
            "reluctant_probability": reluctant_probability,
            "engine_best": None,
        }

    maia_rank, maia_probability = root_move_rank_probability(root_snapshot, best_move["uci"])
    flagged = (
        best_cp >= strong_threshold_cp
        and maia_probability is not None
        and maia_probability < reluctant_probability
    )
    actual_uci = actual_move["uci"] if actual_move else None
    return {
        "flagged": flagged,
        "strong_threshold_cp": strong_threshold_cp,
        "reluctant_probability": reluctant_probability,
        "engine_best": {
            "uci": best_move["uci"],
            "san": best_move["san"],
            "score_cp": best_cp,
            "score_text": best_move["score_text"],
            "pv_san": best_move.get("pv_san", ""),
            "maia_rank": maia_rank,
            "maia_probability": maia_probability,
            "maia_qualifies_threshold": maia_probability is not None and maia_probability >= reluctant_probability,
            "actual_matches": actual_uci == best_move["uci"],
        },
    }


def aggregate_position_stats(games_payload: list[dict[str, object]]) -> dict[str, object]:
    """Compute run-level summary stats for flagged positions."""
    high_positions = [
        position
        for game in games_payload
        for position in game["positions"]
        if position["complexity"]["high"]
    ]
    maia_ranks = [
        int(position["actual_move"]["model_rank"])
        for position in high_positions
        if position["actual_move"]["model_rank"] is not None
    ]
    stockfish_ranks = [
        int(position["actual_move"]["engine_rank"])
        for position in high_positions
        if position["actual_move"]["engine_rank"] is not None
    ]
    maia_engine_bad_positions = [
        position
        for game in games_payload
        for position in game["positions"]
        if position["conflicts"]["maia_high_engine_bad"]["flagged"]
    ]
    maia_engine_bad_moves = sum(
        position["conflicts"]["maia_high_engine_bad"]["move_count"]
        for position in maia_engine_bad_positions
    )
    engine_best_reluctant_positions = [
        position
        for game in games_payload
        for position in game["positions"]
        if position["conflicts"]["engine_best_maia_reluctant"]["flagged"]
    ]
    return {
        "high_complexity_position_count": len(high_positions),
        "maia_actual_move_rank_mean": round(statistics.mean(maia_ranks), 4) if maia_ranks else None,
        "maia_actual_move_rank_coverage": len(maia_ranks),
        "stockfish_actual_move_rank_mean": round(statistics.mean(stockfish_ranks), 4) if stockfish_ranks else None,
        "stockfish_actual_move_rank_coverage": len(stockfish_ranks),
        "maia_high_engine_bad_position_count": len(maia_engine_bad_positions),
        "maia_high_engine_bad_move_count": maia_engine_bad_moves,
        "engine_best_maia_reluctant_position_count": len(engine_best_reluctant_positions),
    }


def build_site_bundle(
    *,
    games_rows: list[dict[str, str]],
    parsed_positions: list[dict[str, str]],
    score_rows: list[dict[str, str]],
    raw_snapshots: dict[str, list[dict[str, object]]],
    stockfish_analysis: dict[str, dict[str, object]],
    summary_payload: dict[str, object],
    maia_engine_gap_threshold_cp: int,
    engine_strong_threshold_cp: int,
    maia_reluctant_probability: float,
    experiment_payloads: dict[str, object] | None = None,
    realizability_position_rows: dict[str, dict[str, object]] | None = None,
    realizability_candidate_rows: dict[str, list[dict[str, object]]] | None = None,
    time_budget_position_rows: dict[str, dict[str, object]] | None = None,
    time_budget_budget_rows: dict[str, list[dict[str, object]]] | None = None,
) -> dict[str, object]:
    all_positions_by_game = positions_by_game(parsed_positions)
    eligible_by_game = positions_by_game(score_rows)
    games_by_id = {row["game_id"]: row for row in games_rows}

    games_payload: list[dict[str, object]] = []
    for game_id in sorted(games_by_id, key=lambda gid: int(games_by_id[gid]["game_index"])):
        game_row = games_by_id[game_id]
        game_positions = eligible_by_game.get(game_id, [])
        parsed_game_rows = all_positions_by_game[game_id]

        payload_positions: list[dict[str, object]] = []
        for row in game_positions:
            parsed_index = next(i for i, candidate in enumerate(parsed_game_rows) if candidate["position_id"] == row["position_id"])
            actual_move = actual_move_payload(parsed_game_rows, parsed_index)
            continuation = continuation_payload(parsed_game_rows, parsed_index)
            root_snapshots = raw_snapshots.get(row["position_id"], [])
            root_snapshot = next((snapshot for snapshot in root_snapshots if snapshot["depth"] == 0), None)
            engine_analysis = stockfish_analysis.get(row["position_id"])
            model_rank, model_probability, model_qualifies = actual_move_model_rank(
                root_snapshot,
                actual_move["uci"] if actual_move else None,
            )
            engine_rank, engine_score_text = actual_move_engine_rank(
                engine_analysis,
                actual_move["uci"] if actual_move else None,
            )
            maia_engine_conflicts = maia_engine_conflict_payload(
                root_snapshot=root_snapshot,
                engine_analysis=engine_analysis,
                actual_move=actual_move,
                gap_threshold_cp=maia_engine_gap_threshold_cp,
            )
            engine_best_reluctance = engine_best_reluctant_payload(
                root_snapshot=root_snapshot,
                engine_analysis=engine_analysis,
                actual_move=actual_move,
                strong_threshold_cp=engine_strong_threshold_cp,
                reluctant_probability=maia_reluctant_probability,
            )

            board_image = str(Path("assets") / "boards" / f"{Path(row['image_path']).name}")
            position_payload = {
                "position_id": row["position_id"],
                "label": position_label(row),
                "game_id": row["game_id"],
                "ply_index": int(row["ply_index"]),
                "fullmove_number": int(row["fullmove_number"]),
                "side_to_move": row["side_to_move"],
                "fen": row["fen"],
                "board_image": board_image,
                "previous_move": {
                    "uci": next((candidate["lastmove_uci"] for candidate in parsed_game_rows if candidate["position_id"] == row["position_id"]), ""),
                    "san": next((candidate["lastmove_san"] for candidate in parsed_game_rows if candidate["position_id"] == row["position_id"]), ""),
                },
                "actual_move": {
                    "available": actual_move is not None,
                    "detail": actual_move,
                    "model_rank": model_rank,
                    "model_probability": model_probability,
                    "model_qualifies_threshold": model_qualifies,
                    "engine_rank": engine_rank,
                    "engine_score_text": engine_score_text,
                },
                "actual_continuation": continuation,
                "complexity": {
                    "score": int(row["complexity_score"]) if row["complexity_score"] else None,
                    "high": row["high_complexity"] == "True",
                    "threshold": int(row["high_complexity_threshold"]),
                    "depth_breakdown": {
                        "depth_0": int(row["depth_0_qualifying_edges"]) if row["depth_0_qualifying_edges"] else None,
                        "depth_1": int(row["depth_1_qualifying_edges"]) if row["depth_1_qualifying_edges"] else None,
                        "depth_2": int(row["depth_2_qualifying_edges"]) if row["depth_2_qualifying_edges"] else None,
                    },
                    "queried_node_count": int(row["queried_node_count"]) if row["queried_node_count"] else 0,
                    "inference_status": row["inference_status"],
                    "error_type": row["failed_error_type"],
                    "error_message": row["failed_error_message"],
                },
                "model": {
                    "available": root_snapshot is not None,
                    "win_prob": root_snapshot["win_prob"] if root_snapshot else None,
                    "qualifying_moves": [
                        {
                            "uci": move,
                            "probability": root_snapshot["qualifying_probabilities"][move],
                        }
                        for move in root_snapshot["qualifying_moves"]
                    ]
                    if root_snapshot
                    else [],
                    "top_moves": top_moves_from_snapshot(root_snapshot, top_k=10) if root_snapshot else [],
                    "tree_nodes_by_depth": snapshot_nodes_by_depth(root_snapshots) if root_snapshots else {"0": [], "1": [], "2": []},
                },
                "engine": {
                    "available": engine_analysis is not None,
                    "moves": engine_analysis.get("moves", []) if engine_analysis else [],
                    "movetime_ms": engine_analysis.get("movetime_ms") if engine_analysis else None,
                    "multipv": engine_analysis.get("multipv") if engine_analysis else None,
                },
                "conflicts": {
                    "maia_high_engine_bad": maia_engine_conflicts,
                    "engine_best_maia_reluctant": engine_best_reluctance,
                },
                "experiments": {
                    "time_budget": {
                        "available": bool(
                            (time_budget_position_rows or {}).get(row["position_id"])
                            or (time_budget_budget_rows or {}).get(row["position_id"])
                        ),
                        "summary": (time_budget_position_rows or {}).get(row["position_id"]),
                        "budget_rows": (time_budget_budget_rows or {}).get(row["position_id"], []),
                    },
                    "realizability": {
                        "available": bool(
                            (realizability_position_rows or {}).get(row["position_id"])
                            or (realizability_candidate_rows or {}).get(row["position_id"])
                        ),
                        "summary": (realizability_position_rows or {}).get(row["position_id"]),
                        "candidates": (realizability_candidate_rows or {}).get(row["position_id"], []),
                    }
                },
            }
            payload_positions.append(position_payload)

        high_count = sum(1 for row in payload_positions if row["complexity"]["high"])
        failed_count = sum(1 for row in payload_positions if row["complexity"]["inference_status"] != "success")
        maia_engine_bad_count = sum(
            1 for row in payload_positions if row["conflicts"]["maia_high_engine_bad"]["flagged"]
        )
        engine_best_reluctant_count = sum(
            1 for row in payload_positions if row["conflicts"]["engine_best_maia_reluctant"]["flagged"]
        )
        games_payload.append(
            {
                "game_id": game_id,
                "game_index": int(game_row["game_index"]),
                "white": game_row["white"],
                "black": game_row["black"],
                "white_elo": int(game_row["white_elo"]),
                "black_elo": int(game_row["black_elo"]),
                "result": game_row["result"],
                "event": game_row["event"],
                "time_control": game_row["time_control"],
                "opening": game_row["opening"],
                "eco": game_row["eco"],
                "ply_count": int(game_row["ply_count"]),
                "move_text": move_text(parsed_game_rows),
                "stats": {
                    "eligible_positions": len(payload_positions),
                    "high_complexity_positions": high_count,
                    "failed_positions": failed_count,
                    "maia_high_engine_bad_positions": maia_engine_bad_count,
                    "engine_best_maia_reluctant_positions": engine_best_reluctant_count,
                    "max_complexity_score": max(
                        (position["complexity"]["score"] or 0 for position in payload_positions),
                        default=0,
                    ),
                },
                "positions": payload_positions,
            }
        )

    aggregate_stats = aggregate_position_stats(games_payload)
    summary_with_stats = dict(summary_payload)
    summary_with_stats.update(aggregate_stats)
    summary_with_stats["conflict_thresholds"] = {
        "maia_engine_gap_threshold_cp": maia_engine_gap_threshold_cp,
        "engine_strong_threshold_cp": engine_strong_threshold_cp,
        "maia_reluctant_probability": maia_reluctant_probability,
    }
    return {
        "generated_at": datetime.now(timezone.utc).isoformat(),
        "summary": summary_with_stats,
        "games": games_payload,
        "experiments": experiment_payloads or {},
    }


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--output-dir", default="outputs/sites/review_site_prototype")
    parser.add_argument("--games-csv", default="outputs/runs/step_04_parse_filter/parsed/games.csv")
    parser.add_argument("--parsed-positions-csv", default="outputs/runs/step_04_parse_filter/parsed/positions.csv")
    parser.add_argument("--position-scores-csv", default="outputs/runs/step_07_complexity_scoring/complexity/position_scores.csv")
    parser.add_argument("--raw-policy-jsonl", default="outputs/runs/step_06_policy_expansion/policy/raw_policy_snapshots.jsonl")
    parser.add_argument("--run-summary-json", default="outputs/runs/step_08_review_bundle/metadata/run_summary.json")
    parser.add_argument("--board-images-dir", default="")
    parser.add_argument("--movetime-ms", type=int, default=120)
    parser.add_argument("--multipv", type=int, default=20)
    parser.add_argument("--refresh-stockfish-cache", action="store_true")
    parser.add_argument("--stockfish-analysis-json", default="")
    parser.add_argument("--rank-bucket-summary-json", default="")
    parser.add_argument("--rank-bucket-bucket-summary-csv", default="")
    parser.add_argument("--time-budget-summary-json", default="")
    parser.add_argument("--time-budget-position-stability-csv", default="")
    parser.add_argument("--time-budget-root-analysis-csv", default="")
    parser.add_argument("--realizability-summary-json", default="")
    parser.add_argument("--realizability-bucket-summary-csv", default="")
    parser.add_argument("--realizability-position-summary-csv", default="")
    parser.add_argument("--realizability-candidate-csv", default="")
    parser.add_argument("--maia-engine-gap-threshold-cp", type=int, default=300)
    parser.add_argument("--engine-strong-threshold-cp", type=int, default=300)
    parser.add_argument("--maia-reluctant-probability", type=float, default=0.10)
    parser.add_argument("--split-games", action="store_true")
    parser.add_argument("--copy-board-assets", action="store_true")
    args = parser.parse_args()

    output_dir = REPO_ROOT / args.output_dir
    site_dir = output_dir / "site"
    data_dir = site_dir / "data"
    assets_dir = site_dir / "assets" / "boards"
    metadata_dir = output_dir / "metadata"
    template_dir = REPO_ROOT / "apps" / "review-site" / "template"

    games_rows = read_csv_rows(REPO_ROOT / args.games_csv)
    parsed_positions = read_csv_rows(REPO_ROOT / args.parsed_positions_csv)
    score_rows = read_csv_rows(REPO_ROOT / args.position_scores_csv)
    raw_snapshots = load_raw_snapshots(REPO_ROOT / args.raw_policy_jsonl)
    summary_payload = read_json(REPO_ROOT / args.run_summary_json)
    if "aggregate_stats" in summary_payload and isinstance(summary_payload["aggregate_stats"], dict):
        summary_payload = summary_payload["aggregate_stats"]
    inferred_board_dir = Path(score_rows[0]["image_path"]).parent if score_rows else None
    board_images_dir = Path(args.board_images_dir) if args.board_images_dir else inferred_board_dir
    if board_images_dir is None:
        raise RuntimeError("Could not determine board image directory for the review site.")

    stockfish_cache_path = output_dir / "data" / "stockfish_root_analysis.json"
    provided_stockfish_json = Path(args.stockfish_analysis_json) if args.stockfish_analysis_json else None
    if provided_stockfish_json and provided_stockfish_json.exists():
        stockfish_analysis = read_json(provided_stockfish_json)
        write_json(stockfish_cache_path, stockfish_analysis)
    else:
        stockfish_analysis = build_stockfish_analysis(
            score_rows,
            cache_path=stockfish_cache_path,
            movetime_ms=args.movetime_ms,
            multipv=args.multipv,
            refresh_cache=args.refresh_stockfish_cache,
        )

    rank_bucket_summary_path = Path(args.rank_bucket_summary_json) if args.rank_bucket_summary_json else None
    rank_bucket_csv_path = Path(args.rank_bucket_bucket_summary_csv) if args.rank_bucket_bucket_summary_csv else None
    experiment_payloads: dict[str, object] = {}
    rank_bucket_summary = read_optional_json(rank_bucket_summary_path)
    rank_bucket_rows = load_optional_csv_rows(rank_bucket_csv_path)
    if rank_bucket_summary or rank_bucket_rows:
        experiment_payloads["rank_bucket_comparison"] = {
            "summary": rank_bucket_summary or {},
            "bucket_rows": rank_bucket_rows,
        }

    time_budget_summary_path = Path(args.time_budget_summary_json) if args.time_budget_summary_json else None
    time_budget_position_csv_path = Path(args.time_budget_position_stability_csv) if args.time_budget_position_stability_csv else None
    time_budget_root_csv_path = Path(args.time_budget_root_analysis_csv) if args.time_budget_root_analysis_csv else None
    time_budget_summary = read_optional_json(time_budget_summary_path)
    time_budget_position_rows = time_budget_position_lookup(load_optional_csv_rows(time_budget_position_csv_path))
    time_budget_budget_rows = time_budget_rows_lookup(load_optional_csv_rows(time_budget_root_csv_path))
    if time_budget_summary:
        experiment_payloads["time_budget_sweep"] = {
            "summary": time_budget_summary,
        }

    realizability_summary_path = Path(args.realizability_summary_json) if args.realizability_summary_json else None
    realizability_bucket_csv_path = Path(args.realizability_bucket_summary_csv) if args.realizability_bucket_summary_csv else None
    realizability_position_csv_path = Path(args.realizability_position_summary_csv) if args.realizability_position_summary_csv else None
    realizability_candidate_csv_path = Path(args.realizability_candidate_csv) if args.realizability_candidate_csv else None
    realizability_summary = read_optional_json(realizability_summary_path)
    realizability_bucket_rows = load_optional_csv_rows(realizability_bucket_csv_path)
    realizability_position_rows = realizability_position_lookup(load_optional_csv_rows(realizability_position_csv_path))
    realizability_candidate_rows = realizability_candidate_lookup(load_optional_csv_rows(realizability_candidate_csv_path))
    if realizability_summary or realizability_bucket_rows:
        experiment_payloads["realizability_probe"] = {
            "summary": realizability_summary or {},
            "bucket_rows": realizability_bucket_rows,
        }

    bundle = build_site_bundle(
        games_rows=games_rows,
        parsed_positions=parsed_positions,
        score_rows=score_rows,
        raw_snapshots=raw_snapshots,
        stockfish_analysis=stockfish_analysis,
        summary_payload=summary_payload,
        maia_engine_gap_threshold_cp=args.maia_engine_gap_threshold_cp,
        engine_strong_threshold_cp=args.engine_strong_threshold_cp,
        maia_reluctant_probability=args.maia_reluctant_probability,
        experiment_payloads=experiment_payloads,
        realizability_position_rows=realizability_position_rows,
        realizability_candidate_rows=realizability_candidate_rows,
        time_budget_position_rows=time_budget_position_rows,
        time_budget_budget_rows=time_budget_budget_rows,
    )

    if site_dir.exists():
        shutil.rmtree(site_dir)
    copy_template(template_dir, site_dir)

    if args.copy_board_assets:
        copy_board_assets_for_bundle(
            bundle,
            source_dir=board_images_dir,
            assets_dir=assets_dir,
        )
    else:
        ensure_board_assets(board_images_dir, assets_dir)

    if args.split_games:
        site_data_summary = write_split_site_data(site_dir, bundle)
    else:
        write_json(data_dir / "site_bundle.json", bundle)
        site_data_summary = {
            "mode": "single_bundle",
            "game_count": len(bundle["games"]),
            "position_count": sum(len(game["positions"]) for game in bundle["games"]),
            "files": {
                "bundle": str(data_dir / "site_bundle.json"),
            },
        }

    open_instructions = {
        "generated_at": datetime.now(timezone.utc).isoformat(),
        "site_root": str(site_dir),
        "entrypoint": str(site_dir / "index.html"),
        "local_server_example": f"python3 -m http.server 8765 -d {site_dir}",
        "browse_url": "http://127.0.0.1:8765",
        "position_count": site_data_summary["position_count"],
        "game_count": site_data_summary["game_count"],
        "aggregate_stats": bundle["summary"],
        "stockfish_cache_refreshed": bool(args.refresh_stockfish_cache),
        "data_mode": site_data_summary["mode"],
        "site_files": site_data_summary["files"],
        "board_assets_mode": "copied" if args.copy_board_assets else "symlink_or_copytree",
    }
    write_json(metadata_dir / "site_build_summary.json", open_instructions)
    (metadata_dir / "site_build_summary.md").write_text(
        "\n".join(
            [
                "# Review Site Prototype",
                "",
                f"- Site root: `{site_dir}`",
                f"- Entry point: `{site_dir / 'index.html'}`",
                f"- Local server example: `{open_instructions['local_server_example']}`",
                f"- Browse URL after serving: `{open_instructions['browse_url']}`",
                f"- Games included: `{open_instructions['game_count']}`",
                f"- Positions included: `{open_instructions['position_count']}`",
                "",
            ]
        )
        + "\n",
        encoding="utf-8",
    )
    print(json.dumps(open_instructions, indent=2))


if __name__ == "__main__":
    main()
