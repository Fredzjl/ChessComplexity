"""Simple probability-tree complexity scoring helpers."""

from __future__ import annotations

from collections import Counter


def score_probability_tree(node_snapshots: list[dict[str, object]]) -> dict[str, object]:
    """Aggregate 3-ply node snapshots into one root-level complexity summary."""
    depth_counter: Counter[int] = Counter()
    queried_node_count = 0

    for snapshot in node_snapshots:
        depth = int(snapshot["depth"])
        qualifying_move_count = int(snapshot["qualifying_move_count"])
        depth_counter[depth] += qualifying_move_count
        queried_node_count += 1

    complexity_score = sum(depth_counter.values())
    return {
        "queried_node_count": queried_node_count,
        "depth_0_qualifying_edges": depth_counter.get(0, 0),
        "depth_1_qualifying_edges": depth_counter.get(1, 0),
        "depth_2_qualifying_edges": depth_counter.get(2, 0),
        "complexity_score": complexity_score,
    }
