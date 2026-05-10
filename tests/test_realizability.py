from __future__ import annotations

from src.analysis.realizability import (
    acceptable_moves,
    candidate_viable_threshold,
    scalar_realizability_score,
    select_root_candidates,
)


def test_acceptable_moves_respects_viable_and_local_slack() -> None:
    moves = [
        {"uci": "a", "rank": 1, "score_sort_value": 300},
        {"uci": "b", "rank": 2, "score_sort_value": 260},
        {"uci": "c", "rank": 3, "score_sort_value": 210},
        {"uci": "d", "rank": 4, "score_sort_value": 150},
    ]
    accepted, cutoff, penalty = acceptable_moves(
        moves,
        viable_threshold=220,
        local_slack_cp=80,
    )
    assert cutoff == 220
    assert [move["uci"] for move in accepted] == ["a", "b"]
    assert penalty == 90


def test_candidate_viable_threshold_keeps_strictest_floor() -> None:
    threshold = candidate_viable_threshold(
        root_eval=120,
        candidate_value=260,
        absolute_floor_cp=80,
        max_total_drop_cp=100,
        retain_gain_ratio=0.7,
    )
    assert threshold == 218


def test_select_root_candidates_forces_actual_move_when_missing() -> None:
    root_analysis = {
        "moves": [
            {"uci": "e2e4", "san": "e4", "rank": 1, "score_sort_value": 180},
            {"uci": "d2d4", "san": "d4", "rank": 2, "score_sort_value": 130},
            {"uci": "g1f3", "san": "Nf3", "rank": 3, "score_sort_value": 20},
        ]
    }
    candidates = select_root_candidates(
        root_analysis=root_analysis,
        actual_move_uci="b1c3",
        candidate_cfg={
            "top_k_root_candidates": 3,
            "near_best_window_cp": 80,
            "absolute_advantage_floor_cp": 150,
            "min_incremental_gain_cp": 80,
        },
    )
    candidate_uci = [row["candidate_uci"] for row in candidates]
    assert candidate_uci == ["e2e4", "d2d4", "b1c3"]
    assert candidates[-1]["forced_include_actual"] is True


def test_scalar_realizability_score_rewards_wider_safer_lines() -> None:
    config = {
        "scalar_score": {
            "width_target": 4,
            "slack_target_cp": 120,
            "burden_cap_plies": 4,
            "penalty_cap_cp": 200,
            "weight_width": 0.28,
            "weight_survival": 0.22,
            "weight_slack": 0.12,
            "weight_non_unique": 0.18,
            "weight_non_fragile": 0.15,
            "weight_fast_conversion": 0.05,
        }
    }
    easy = scalar_realizability_score(
        acceptable_width_player_mean=3.5,
        survival_rate_after_opponent=0.9,
        mean_margin_to_viable_cp=90,
        unique_burden_plies=0,
        deviation_penalty_cp_mean=20,
        depth4_survival_rate=0.8,
        config=config,
    )
    brittle = scalar_realizability_score(
        acceptable_width_player_mean=0.8,
        survival_rate_after_opponent=0.2,
        mean_margin_to_viable_cp=10,
        unique_burden_plies=4,
        deviation_penalty_cp_mean=180,
        depth4_survival_rate=0.0,
        config=config,
    )
    assert easy > brittle
    assert easy > 60
    assert brittle < 30
