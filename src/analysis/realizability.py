"""Experiment 3: realizability probe for engine-valued candidate moves."""

from __future__ import annotations

import csv
import json
import math
import os
import statistics
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


def load_yaml(path: Path) -> dict[str, object]:
    return yaml.safe_load(path.read_text(encoding="utf-8"))


def load_root_snapshots(path: Path) -> dict[str, dict[str, object]]:
    roots: dict[str, dict[str, object]] = {}
    with path.open("r", encoding="utf-8") as handle:
        for line in handle:
            snapshot = json.loads(line)
            if int(snapshot["depth"]) != 0:
                continue
            roots[str(snapshot["root_position_id"])] = snapshot
    return roots


def clamp01(value: float) -> float:
    return max(0.0, min(1.0, value))


def safe_mean(values: list[int | float]) -> float | None:
    if not values:
        return None
    return float(statistics.mean(values))


def safe_median(values: list[int | float]) -> float | None:
    if not values:
        return None
    return float(statistics.median(values))


def rounded_or_none(value: float | None, digits: int = 4) -> float | None:
    if value is None:
        return None
    return round(float(value), digits)


def pearson_correlation(xs: list[float], ys: list[float]) -> float | None:
    if len(xs) < 2 or len(xs) != len(ys):
        return None
    x_mean = statistics.mean(xs)
    y_mean = statistics.mean(ys)
    num = sum((x - x_mean) * (y - y_mean) for x, y in zip(xs, ys))
    den_x = math.sqrt(sum((x - x_mean) ** 2 for x in xs))
    den_y = math.sqrt(sum((y - y_mean) ** 2 for y in ys))
    if den_x == 0 or den_y == 0:
        return None
    return float(num / (den_x * den_y))


def side_to_move_elo(row: dict[str, str]) -> int:
    return int(row["white_elo"]) if row["side_to_move"] == "white" else int(row["black_elo"])


def elo_bucket_start(elo: int, width: int) -> int:
    return (elo // width) * width


def elo_bucket_label(start: int, width: int) -> str:
    return f"{start}-{start + width - 1}"


def move_score_value(move: dict[str, object]) -> int:
    if move.get("score_sort_value") is not None:
        return int(move["score_sort_value"])
    if move.get("score_cp") is not None:
        return int(move["score_cp"])
    mate = move.get("score_mate")
    if mate is None:
        return 0
    sign = 1 if int(mate) > 0 else -1
    return sign * (100_000 - min(abs(int(mate)), 99_999))


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


@dataclass(slots=True)
class ProbePosition:
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
    player_elo: int
    image_path: str
    complexity_score: int
    high_complexity: bool
    actual_move_uci: str | None
    actual_move_san: str | None


def scoped_positions(
    *,
    score_rows: list[dict[str, str]],
    parsed_positions: list[dict[str, str]],
    config: dict[str, object],
) -> list[ProbePosition]:
    actual_lookup = actual_move_lookup(parsed_positions)
    candidate_cfg = config["candidate_selection"]
    complex_only = bool(candidate_cfg.get("complex_only", False))
    complexity_threshold = int(candidate_cfg.get("complexity_threshold", 0))
    max_positions = candidate_cfg.get("max_positions")

    rows: list[ProbePosition] = []
    for row in score_rows:
        if row.get("inference_status") != "success":
            continue
        complexity_score = int(row["complexity_score"]) if row["complexity_score"] else 0
        high_complexity = row.get("high_complexity") == "True"
        if complex_only and not (high_complexity and complexity_score >= complexity_threshold):
            continue
        actual = actual_lookup.get(row["position_id"], {})
        rows.append(
            ProbePosition(
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
                player_elo=side_to_move_elo(row),
                image_path=row["image_path"],
                complexity_score=complexity_score,
                high_complexity=high_complexity,
                actual_move_uci=actual.get("actual_move_uci"),
                actual_move_san=actual.get("actual_move_san"),
            )
        )
    rows.sort(key=lambda item: (item.game_id, item.ply_index))
    if max_positions is not None:
        rows = rows[: int(max_positions)]
    return rows


def root_move_probability(
    root_snapshot: dict[str, object] | None,
    move_uci: str | None,
) -> tuple[int | None, float | None]:
    if not root_snapshot or not move_uci:
        return None, None
    for rank, (uci, probability) in enumerate(root_snapshot["move_probs"].items(), start=1):
        if uci == move_uci:
            return rank, float(probability)
    return None, None


def acceptable_moves(
    moves: list[dict[str, object]],
    *,
    viable_threshold: int,
    local_slack_cp: int,
) -> tuple[list[dict[str, object]], int, int]:
    if not moves:
        return [], viable_threshold, 0
    best_value = move_score_value(moves[0])
    cutoff = max(best_value - local_slack_cp, viable_threshold)
    accepted = [move for move in moves if move_score_value(move) >= cutoff]
    penalty = 0
    for move in moves:
        if move_score_value(move) < cutoff:
            penalty = best_value - move_score_value(move)
            break
    return accepted, cutoff, penalty


def candidate_viable_threshold(
    *,
    root_eval: int,
    candidate_value: int,
    absolute_floor_cp: int,
    max_total_drop_cp: int,
    retain_gain_ratio: float,
) -> int:
    gain = candidate_value - root_eval
    retained_gain_floor = root_eval + int(round(retain_gain_ratio * max(gain, 0)))
    return max(
        int(absolute_floor_cp),
        int(candidate_value - max_total_drop_cp),
        int(retained_gain_floor),
    )


def scalar_realizability_score(
    *,
    acceptable_width_player_mean: float | None,
    survival_rate_after_opponent: float | None,
    mean_margin_to_viable_cp: float | None,
    unique_burden_plies: int,
    deviation_penalty_cp_mean: float | None,
    depth4_survival_rate: float | None,
    config: dict[str, object],
) -> float:
    score_cfg = config["scalar_score"]
    width_target = float(score_cfg["width_target"])
    slack_target_cp = float(score_cfg["slack_target_cp"])
    burden_cap_plies = float(score_cfg["burden_cap_plies"])
    penalty_cap_cp = float(score_cfg["penalty_cap_cp"])

    f_width = clamp01((acceptable_width_player_mean or 0.0) / width_target)
    f_survival = clamp01(survival_rate_after_opponent or 0.0)
    f_slack = clamp01(max(mean_margin_to_viable_cp or 0.0, 0.0) / slack_target_cp)
    r_unique = clamp01(unique_burden_plies / burden_cap_plies)
    r_fragile = clamp01(max(deviation_penalty_cp_mean or 0.0, 0.0) / penalty_cap_cp)
    r_slow = clamp01(1.0 - (depth4_survival_rate or 0.0))

    score = 100.0 * (
        float(score_cfg["weight_width"]) * f_width
        + float(score_cfg["weight_survival"]) * f_survival
        + float(score_cfg["weight_slack"]) * f_slack
        + float(score_cfg["weight_non_unique"]) * (1.0 - r_unique)
        + float(score_cfg["weight_non_fragile"]) * (1.0 - r_fragile)
        + float(score_cfg["weight_fast_conversion"]) * (1.0 - r_slow)
    )
    return round(score, 2)


def select_root_candidates(
    *,
    root_analysis: dict[str, object],
    actual_move_uci: str | None,
    candidate_cfg: dict[str, object],
) -> list[dict[str, object]]:
    moves = list(root_analysis.get("moves", []))
    if not moves:
        return []
    top_k = int(candidate_cfg["top_k_root_candidates"])
    near_best_window_cp = int(candidate_cfg["near_best_window_cp"])
    absolute_advantage_floor_cp = int(candidate_cfg["absolute_advantage_floor_cp"])
    min_incremental_gain_cp = int(candidate_cfg["min_incremental_gain_cp"])

    root_eval = move_score_value(moves[0])
    included: dict[str, dict[str, object]] = {}
    for move in moves[:top_k]:
        value = move_score_value(move)
        qualifies = (
            (root_eval - value) <= near_best_window_cp
            or value >= absolute_advantage_floor_cp
            or (value - root_eval) >= min_incremental_gain_cp
            or int(move["rank"]) == 1
        )
        if not qualifies:
            continue
        included[str(move["uci"])] = {
            "candidate_uci": str(move["uci"]),
            "candidate_san": str(move["san"]),
            "root_rank": int(move["rank"]),
            "role": "engine_best" if int(move["rank"]) == 1 else "engine_topk",
            "forced_include_actual": False,
        }

    if actual_move_uci and actual_move_uci not in included:
        included[actual_move_uci] = {
            "candidate_uci": actual_move_uci,
            "candidate_san": None,
            "root_rank": None,
            "role": "actual_move",
            "forced_include_actual": True,
        }

    candidates = list(included.values())
    candidates.sort(
        key=lambda item: (
            0 if item["role"] == "engine_best" else 1,
            item["root_rank"] if item["root_rank"] is not None else 999,
            item["candidate_uci"],
        )
    )
    return candidates


def branch_widths_summary(widths: list[int]) -> tuple[float | None, int | None]:
    if not widths:
        return None, None
    return round(float(statistics.mean(widths)), 4), min(widths)


def auto_worker_count(requested: str | int | None, position_count: int) -> int:
    if isinstance(requested, int):
        return max(1, min(requested, position_count))
    if isinstance(requested, str) and requested != "auto":
        return max(1, min(int(requested), position_count))
    cpu_count = os.cpu_count() or 4
    return max(1, min(position_count, cpu_count - 2 if cpu_count > 4 else cpu_count))


def chunk_positions(rows: list[ProbePosition], chunk_count: int) -> list[list[ProbePosition]]:
    if chunk_count <= 1:
        return [rows]
    chunks: list[list[ProbePosition]] = [[] for _ in range(chunk_count)]
    for index, row in enumerate(rows):
        chunks[index % chunk_count].append(row)
    return [chunk for chunk in chunks if chunk]


def analyze_candidate(
    *,
    adapter: StockfishAdapter,
    board: chess.Board,
    root_color: chess.Color,
    root_eval: int,
    position: ProbePosition,
    candidate: dict[str, object],
    root_snapshot: dict[str, object] | None,
    config: dict[str, object],
) -> dict[str, object]:
    acceptable_cfg = config["acceptable_line"]
    engine_cfg = config["engine_analysis"]
    local_slack_cp = int(acceptable_cfg["local_slack_cp"])
    narrow_threshold = 2

    candidate_move = chess.Move.from_uci(str(candidate["candidate_uci"]))
    candidate_san = candidate["candidate_san"] or board.san(candidate_move)
    candidate_board = board.copy(stack=False)
    candidate_board.push(candidate_move)

    adapter.movetime_ms = int(engine_cfg["node_movetime_ms"])
    adapter.multipv = int(engine_cfg["node_multipv"])
    root_after_candidate = adapter.analyse_board(candidate_board, pov_color=root_color)
    if not root_after_candidate["moves"]:
        raise RuntimeError(f"No opponent replies returned for {position.position_id} {candidate_move.uci()}")

    candidate_value = move_score_value(root_after_candidate["moves"][0])
    viable_threshold = candidate_viable_threshold(
        root_eval=root_eval,
        candidate_value=candidate_value,
        absolute_floor_cp=int(acceptable_cfg["absolute_floor_cp"]),
        max_total_drop_cp=int(acceptable_cfg["max_total_drop_cp"]),
        retain_gain_ratio=float(acceptable_cfg["retain_gain_ratio"]),
    )

    opponent_moves = list(root_after_candidate["moves"])
    opponent_refutation_count = sum(1 for move in opponent_moves if move_score_value(move) < viable_threshold)

    player_widths: list[int] = []
    player_widths_d1: list[int] = []
    player_widths_d3: list[int] = []
    margins_to_viable: list[int] = []
    deviation_penalties: list[int] = []
    unique_burden_plies = 0
    longest_narrow_streak = 0
    survived_after_opponent = 0
    depth4_surviving_lines = 0
    depth4_lines = 0

    for opponent_move in opponent_moves:
        board_after_opp = candidate_board.copy(stack=False)
        board_after_opp.push(chess.Move.from_uci(str(opponent_move["uci"])))

        player_node = adapter.analyse_board(board_after_opp, pov_color=root_color)
        acceptable_player_moves, _, penalty_d1 = acceptable_moves(
            player_node["moves"],
            viable_threshold=viable_threshold,
            local_slack_cp=local_slack_cp,
        )
        width_d1 = len(acceptable_player_moves)
        player_widths.append(width_d1)
        player_widths_d1.append(width_d1)
        deviation_penalties.append(penalty_d1)
        if width_d1 > 0:
            survived_after_opponent += 1
            margins_to_viable.extend(move_score_value(move) - viable_threshold for move in acceptable_player_moves)
            if width_d1 <= narrow_threshold:
                unique_burden_plies += 1
                longest_narrow_streak = max(longest_narrow_streak, 1)

        if not acceptable_player_moves:
            continue

        chosen_player_move = acceptable_player_moves[0]
        board_after_player = board_after_opp.copy(stack=False)
        board_after_player.push(chess.Move.from_uci(str(chosen_player_move["uci"])))

        opponent_node = adapter.analyse_board(board_after_player, pov_color=root_color)
        if not opponent_node["moves"]:
            continue

        best_opponent_reply = opponent_node["moves"][0]
        board_after_best_resistance = board_after_player.copy(stack=False)
        board_after_best_resistance.push(chess.Move.from_uci(str(best_opponent_reply["uci"])))

        player_node_d3 = adapter.analyse_board(board_after_best_resistance, pov_color=root_color)
        acceptable_player_moves_d3, _, penalty_d3 = acceptable_moves(
            player_node_d3["moves"],
            viable_threshold=viable_threshold,
            local_slack_cp=local_slack_cp,
        )
        width_d3 = len(acceptable_player_moves_d3)
        player_widths.append(width_d3)
        player_widths_d3.append(width_d3)
        deviation_penalties.append(penalty_d3)
        depth4_lines += 1
        if width_d3 > 0:
            depth4_surviving_lines += 1
            margins_to_viable.extend(move_score_value(move) - viable_threshold for move in acceptable_player_moves_d3)
        branch_streak = 0
        if 0 < width_d1 <= narrow_threshold:
            branch_streak = 1
        if 0 < width_d3 <= narrow_threshold:
            unique_burden_plies += 1
            branch_streak = branch_streak + 1 if branch_streak else 1
        longest_narrow_streak = max(longest_narrow_streak, branch_streak)

    acceptable_width_player_mean, acceptable_width_player_min = branch_widths_summary(player_widths)
    acceptable_width_player_d1 = safe_mean(player_widths_d1)
    acceptable_width_d3 = safe_mean(player_widths_d3)
    survival_rate_after_opponent = (
        round(survived_after_opponent / len(opponent_moves), 4) if opponent_moves else None
    )
    opponent_refutation_density = (
        round(opponent_refutation_count / len(opponent_moves), 4) if opponent_moves else None
    )
    depth4_survival_rate = (
        round(depth4_surviving_lines / depth4_lines, 4) if depth4_lines else 0.0
    )
    mean_margin_to_viable_cp = safe_mean(margins_to_viable)
    deviation_penalty_cp_mean = safe_mean(deviation_penalties)
    deviation_penalty_cp_max = max(deviation_penalties) if deviation_penalties else 0
    conversion_success_within_horizon = depth4_surviving_lines > 0
    conversion_horizon_plies = 4 if conversion_success_within_horizon else (2 if survived_after_opponent else None)

    maia_rank, maia_probability = root_move_probability(root_snapshot, str(candidate["candidate_uci"]))
    realizability_score = scalar_realizability_score(
        acceptable_width_player_mean=acceptable_width_player_mean,
        survival_rate_after_opponent=survival_rate_after_opponent,
        mean_margin_to_viable_cp=mean_margin_to_viable_cp,
        unique_burden_plies=unique_burden_plies,
        deviation_penalty_cp_mean=deviation_penalty_cp_mean,
        depth4_survival_rate=depth4_survival_rate,
        config=config,
    )

    return {
        "position_id": position.position_id,
        "game_id": position.game_id,
        "ply_index": position.ply_index,
        "fullmove_number": position.fullmove_number,
        "side_to_move": position.side_to_move,
        "player_elo": position.player_elo,
        "white_elo": position.white_elo,
        "black_elo": position.black_elo,
        "white": position.white,
        "black": position.black,
        "fen": position.fen,
        "image_path": position.image_path,
        "complexity_score": position.complexity_score,
        "high_complexity": position.high_complexity,
        "candidate_uci": str(candidate["candidate_uci"]),
        "candidate_san": candidate_san,
        "candidate_role": str(candidate["role"]),
        "forced_include_actual": bool(candidate["forced_include_actual"]),
        "is_actual_move": position.actual_move_uci == str(candidate["candidate_uci"]),
        "is_engine_best": str(candidate["role"]) == "engine_best",
        "actual_move_uci": position.actual_move_uci,
        "actual_move_san": position.actual_move_san,
        "root_rank": candidate["root_rank"],
        "root_eval_cp": root_eval,
        "root_value_cp": candidate_value,
        "initial_gain_cp": candidate_value - root_eval,
        "distance_from_best_cp": root_eval - candidate_value,
        "viable_threshold_cp": viable_threshold,
        "acceptable_width_player_d1": round(acceptable_width_player_d1, 4) if acceptable_width_player_d1 is not None else None,
        "acceptable_width_player_mean": round(acceptable_width_player_mean, 4) if acceptable_width_player_mean is not None else None,
        "acceptable_width_player_min": acceptable_width_player_min,
        "acceptable_width_d3": round(acceptable_width_d3, 4) if acceptable_width_d3 is not None else None,
        "survival_rate_after_opponent": survival_rate_after_opponent,
        "opponent_refutation_density": opponent_refutation_density,
        "depth4_survival_rate": depth4_survival_rate,
        "unique_burden_plies": unique_burden_plies,
        "longest_narrow_streak": longest_narrow_streak,
        "deviation_penalty_cp_mean": round(deviation_penalty_cp_mean, 4) if deviation_penalty_cp_mean is not None else None,
        "deviation_penalty_cp_max": deviation_penalty_cp_max,
        "mean_margin_to_viable_cp": round(mean_margin_to_viable_cp, 4) if mean_margin_to_viable_cp is not None else None,
        "conversion_horizon_plies": conversion_horizon_plies,
        "conversion_success_within_horizon": conversion_success_within_horizon,
        "maia_rank": maia_rank,
        "maia_probability": round(maia_probability, 6) if maia_probability is not None else None,
        "realizability_score_v0": realizability_score,
    }


def analyze_position(
    position: ProbePosition,
    *,
    root_snapshot: dict[str, object] | None,
    config: dict[str, object],
    binary_path: str | None,
    threads_per_worker: int,
    hash_mb: int,
) -> dict[str, object]:
    engine_cfg = config["engine_analysis"]
    candidate_cfg = config["candidate_selection"]
    board = chess.Board(position.fen)
    root_color = board.turn

    adapter = StockfishAdapter(
        binary_path=binary_path,
        threads=threads_per_worker,
        hash_mb=hash_mb,
        movetime_ms=int(engine_cfg["root_movetime_ms"]),
        multipv=int(engine_cfg["root_multipv"]),
    )
    adapter.load()
    try:
        root_analysis = adapter.analyse_board(board, pov_color=root_color)
        if not root_analysis["moves"]:
            raise RuntimeError(f"No root analysis moves for {position.position_id}")
        root_eval = move_score_value(root_analysis["moves"][0])
        candidates = select_root_candidates(
            root_analysis=root_analysis,
            actual_move_uci=position.actual_move_uci,
            candidate_cfg=candidate_cfg,
        )
        candidate_rows = [
            analyze_candidate(
                adapter=adapter,
                board=board,
                root_color=root_color,
                root_eval=root_eval,
                position=position,
                candidate=candidate,
                root_snapshot=root_snapshot,
                config=config,
            )
            for candidate in candidates
        ]
    finally:
        adapter.close()

    candidate_rows.sort(
        key=lambda row: (
            -float(row["realizability_score_v0"]),
            0 if row["is_actual_move"] else 1,
            row["candidate_uci"],
        )
    )

    actual_row = next((row for row in candidate_rows if row["is_actual_move"]), None)
    engine_best_row = next((row for row in candidate_rows if row["is_engine_best"]), None)
    top_realizable_row = candidate_rows[0] if candidate_rows else None
    actual_delta = None
    if actual_row and engine_best_row:
        actual_delta = round(
            float(actual_row["realizability_score_v0"]) - float(engine_best_row["realizability_score_v0"]),
            4,
        )

    position_summary = {
        "position_id": position.position_id,
        "game_id": position.game_id,
        "ply_index": position.ply_index,
        "fullmove_number": position.fullmove_number,
        "side_to_move": position.side_to_move,
        "player_elo": position.player_elo,
        "white": position.white,
        "black": position.black,
        "complexity_score": position.complexity_score,
        "image_path": position.image_path,
        "candidate_count": len(candidate_rows),
        "actual_move_uci": position.actual_move_uci,
        "actual_move_san": position.actual_move_san,
        "actual_candidate_available": actual_row is not None,
        "actual_realizability_score_v0": actual_row["realizability_score_v0"] if actual_row else None,
        "actual_maia_probability": actual_row["maia_probability"] if actual_row else None,
        "actual_maia_rank": actual_row["maia_rank"] if actual_row else None,
        "engine_best_uci": engine_best_row["candidate_uci"] if engine_best_row else None,
        "engine_best_san": engine_best_row["candidate_san"] if engine_best_row else None,
        "engine_best_realizability_score_v0": engine_best_row["realizability_score_v0"] if engine_best_row else None,
        "engine_best_maia_probability": engine_best_row["maia_probability"] if engine_best_row else None,
        "engine_best_maia_rank": engine_best_row["maia_rank"] if engine_best_row else None,
        "top_realizability_uci": top_realizable_row["candidate_uci"] if top_realizable_row else None,
        "top_realizability_san": top_realizable_row["candidate_san"] if top_realizable_row else None,
        "top_realizability_score_v0": top_realizable_row["realizability_score_v0"] if top_realizable_row else None,
        "actual_minus_engine_best_realizability": actual_delta,
        "actual_matches_engine_best": bool(actual_row and engine_best_row and actual_row["candidate_uci"] == engine_best_row["candidate_uci"]),
        "actual_matches_top_realizability": bool(actual_row and top_realizable_row and actual_row["candidate_uci"] == top_realizable_row["candidate_uci"]),
        "actual_beats_engine_best": bool(actual_delta is not None and actual_delta > 0),
    }
    return {
        "candidate_rows": candidate_rows,
        "position_summary": position_summary,
    }


def analyze_position_batch(task: dict[str, object]) -> list[dict[str, object]]:
    config = task["config"]
    snapshot_lookup = task["root_snapshots"]
    results: list[dict[str, object]] = []
    for position_payload in task["positions"]:
        position = ProbePosition(**position_payload)
        result = analyze_position(
            position=position,
            root_snapshot=snapshot_lookup.get(position.position_id),
            config=config,
            binary_path=task.get("binary_path"),
            threads_per_worker=int(task["threads_per_worker"]),
            hash_mb=int(task["hash_mb"]),
        )
        results.append(result)
    return results


def build_bucket_summary_rows(
    *,
    position_rows: list[dict[str, object]],
    candidate_rows: list[dict[str, object]],
    min_player_elo: int,
    elo_bucket_width: int,
) -> list[dict[str, object]]:
    eligible_positions = [
        row
        for row in position_rows
        if int(row["player_elo"]) >= min_player_elo
    ]
    candidate_by_bucket: dict[int, list[dict[str, object]]] = {}
    for row in candidate_rows:
        if int(row["player_elo"]) < min_player_elo:
            continue
        bucket_start = elo_bucket_start(int(row["player_elo"]), elo_bucket_width)
        candidate_by_bucket.setdefault(bucket_start, []).append(row)

    grouped: dict[int, list[dict[str, object]]] = {}
    for row in eligible_positions:
        bucket_start = elo_bucket_start(int(row["player_elo"]), elo_bucket_width)
        grouped.setdefault(bucket_start, []).append(row)

    summary_rows: list[dict[str, object]] = []
    for bucket_start in sorted(grouped):
        rows = grouped[bucket_start]
        bucket_candidates = candidate_by_bucket.get(bucket_start, [])
        actual_scores = [
            float(row["actual_realizability_score_v0"])
            for row in rows
            if row["actual_realizability_score_v0"] is not None
        ]
        engine_scores = [
            float(row["engine_best_realizability_score_v0"])
            for row in rows
            if row["engine_best_realizability_score_v0"] is not None
        ]
        deltas = [
            float(row["actual_minus_engine_best_realizability"])
            for row in rows
            if row["actual_minus_engine_best_realizability"] is not None
        ]
        maia_probs = [
            float(row["maia_probability"])
            for row in bucket_candidates
            if row["maia_probability"] is not None
        ]
        realizability_scores = [float(row["realizability_score_v0"]) for row in bucket_candidates]
        bucket_corr = (
            pearson_correlation(maia_probs, realizability_scores)
            if len(maia_probs) >= 2 and len(maia_probs) == len(realizability_scores)
            else None
        )
        summary_rows.append(
            {
                "elo_bucket_start": bucket_start,
                "elo_bucket_label": elo_bucket_label(bucket_start, elo_bucket_width),
                "position_count": len(rows),
                "candidate_count": len(bucket_candidates),
                "actual_candidate_count": len(actual_scores),
                "engine_best_candidate_count": len(engine_scores),
                "mean_actual_realizability": round(safe_mean(actual_scores), 4) if actual_scores else None,
                "mean_engine_best_realizability": round(safe_mean(engine_scores), 4) if engine_scores else None,
                "mean_actual_minus_engine_best": round(safe_mean(deltas), 4) if deltas else None,
                "actual_beats_engine_best_rate": round(
                    sum(1 for row in rows if row["actual_beats_engine_best"]) / len(rows),
                    4,
                ) if rows else None,
                "actual_matches_top_realizability_rate": round(
                    sum(1 for row in rows if row["actual_matches_top_realizability"]) / len(rows),
                    4,
                ) if rows else None,
                "candidate_level_maia_probability_realizability_corr": rounded_or_none(bucket_corr),
            }
        )
    return summary_rows


def build_summary_payload(
    *,
    config: dict[str, object],
    position_rows: list[dict[str, object]],
    candidate_rows: list[dict[str, object]],
    bucket_rows: list[dict[str, object]],
) -> dict[str, object]:
    actual_scores = [
        float(row["actual_realizability_score_v0"])
        for row in position_rows
        if row["actual_realizability_score_v0"] is not None
    ]
    engine_scores = [
        float(row["engine_best_realizability_score_v0"])
        for row in position_rows
        if row["engine_best_realizability_score_v0"] is not None
    ]
    deltas = [
        float(row["actual_minus_engine_best_realizability"])
        for row in position_rows
        if row["actual_minus_engine_best_realizability"] is not None
    ]
    maia_probs = [
        float(row["maia_probability"])
        for row in candidate_rows
        if row["maia_probability"] is not None
    ]
    realizability_scores = [float(row["realizability_score_v0"]) for row in candidate_rows]
    actual_candidate_rows = [row for row in candidate_rows if row["is_actual_move"]]
    forced_actual_count = sum(1 for row in candidate_rows if row["forced_include_actual"])

    overall_corr = (
        pearson_correlation(maia_probs, realizability_scores)
        if len(maia_probs) >= 2 and len(maia_probs) == len(realizability_scores)
        else None
    )

    return {
        "experiment_name": config["experiment_name"],
        "position_count": len(position_rows),
        "candidate_count": len(candidate_rows),
        "actual_candidate_count": len(actual_scores),
        "engine_best_candidate_count": len(engine_scores),
        "forced_actual_candidate_count": forced_actual_count,
        "mean_candidate_realizability": rounded_or_none(safe_mean(realizability_scores)),
        "median_candidate_realizability": rounded_or_none(safe_median(realizability_scores)),
        "mean_actual_realizability": rounded_or_none(safe_mean(actual_scores)),
        "mean_engine_best_realizability": rounded_or_none(safe_mean(engine_scores)),
        "mean_actual_minus_engine_best": rounded_or_none(safe_mean(deltas)),
        "actual_beats_engine_best_rate": round(
            sum(1 for row in position_rows if row["actual_beats_engine_best"]) / len(position_rows),
            4,
        ) if position_rows else None,
        "actual_matches_top_realizability_rate": round(
            sum(1 for row in position_rows if row["actual_matches_top_realizability"]) / len(position_rows),
            4,
        ) if position_rows else None,
        "candidate_level_maia_probability_realizability_corr": rounded_or_none(overall_corr),
        "actual_move_maia_probability_mean": rounded_or_none(
            safe_mean(
                [float(row["maia_probability"]) for row in actual_candidate_rows if row["maia_probability"] is not None]
            )
        ) if actual_candidate_rows else None,
        "population": {
            "complex_only": bool(config["candidate_selection"].get("complex_only", False)),
            "complexity_threshold": int(config["candidate_selection"].get("complexity_threshold", 0)),
            "min_player_elo_bucketed": int(config["analysis"].get("min_player_elo_bucketed", 1000)),
            "elo_bucket_width": int(config["analysis"].get("elo_bucket_width", 100)),
        },
        "engine": {
            "root_movetime_ms": int(config["engine_analysis"]["root_movetime_ms"]),
            "node_movetime_ms": int(config["engine_analysis"]["node_movetime_ms"]),
            "root_multipv": int(config["engine_analysis"]["root_multipv"]),
            "node_multipv": int(config["engine_analysis"]["node_multipv"]),
            "threads_per_worker": int(config["engine_analysis"].get("threads_per_worker", 1)),
            "max_workers": config["engine_analysis"].get("max_workers", "auto"),
        },
        "bucket_count": len(bucket_rows),
    }


def run_realizability_probe(
    *,
    config: dict[str, object],
    score_rows: list[dict[str, str]],
    parsed_positions: list[dict[str, str]],
    root_snapshots: dict[str, dict[str, object]],
) -> tuple[list[dict[str, object]], list[dict[str, object]], list[dict[str, object]], dict[str, object]]:
    positions = scoped_positions(score_rows=score_rows, parsed_positions=parsed_positions, config=config)
    engine_cfg = config["engine_analysis"]
    max_workers = auto_worker_count(engine_cfg.get("max_workers"), len(positions)) if positions else 1
    chunks = chunk_positions(positions, max_workers)

    tasks = [
        {
            "positions": [asdict(position) for position in chunk],
            "config": config,
            "root_snapshots": {position.position_id: root_snapshots.get(position.position_id) for position in chunk},
            "binary_path": engine_cfg.get("binary_path"),
            "threads_per_worker": int(engine_cfg.get("threads_per_worker", 1)),
            "hash_mb": int(engine_cfg.get("hash_mb", 128)),
        }
        for chunk in chunks
    ]

    position_rows: list[dict[str, object]] = []
    candidate_rows: list[dict[str, object]] = []
    with ProcessPoolExecutor(max_workers=max_workers) as executor:
        futures = [executor.submit(analyze_position_batch, task) for task in tasks]
        for future in as_completed(futures):
            for result in future.result():
                position_rows.append(result["position_summary"])
                candidate_rows.extend(result["candidate_rows"])

    position_rows.sort(key=lambda row: (row["game_id"], int(row["ply_index"])))
    candidate_rows.sort(
        key=lambda row: (row["game_id"], int(row["ply_index"]), row["candidate_role"], -float(row["realizability_score_v0"]))
    )

    analysis_cfg = config["analysis"]
    bucket_rows = build_bucket_summary_rows(
        position_rows=position_rows,
        candidate_rows=candidate_rows,
        min_player_elo=int(analysis_cfg.get("min_player_elo_bucketed", 1000)),
        elo_bucket_width=int(analysis_cfg.get("elo_bucket_width", 100)),
    )
    summary_payload = build_summary_payload(
        config=config,
        position_rows=position_rows,
        candidate_rows=candidate_rows,
        bucket_rows=bucket_rows,
    )
    return positions, position_rows, candidate_rows, bucket_rows, summary_payload
