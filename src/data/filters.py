"""Position filtering helpers for middlegame candidate selection."""

from __future__ import annotations

from collections import Counter


def position_skip_reasons(
    record: dict[str, object],
    *,
    min_fullmove: int,
    max_fullmove: int,
    min_remaining_pieces_per_side: int,
) -> list[str]:
    """Return explicit skip reasons for one position record."""
    reasons: list[str] = []
    fullmove_number = int(record["fullmove_number"])
    white_pieces = int(record["remaining_white_pieces"])
    black_pieces = int(record["remaining_black_pieces"])

    if fullmove_number < min_fullmove:
        reasons.append("before_min_fullmove")
    if fullmove_number > max_fullmove:
        reasons.append("after_max_fullmove")
    if white_pieces < min_remaining_pieces_per_side:
        reasons.append("white_below_piece_threshold")
    if black_pieces < min_remaining_pieces_per_side:
        reasons.append("black_below_piece_threshold")

    return reasons


def apply_middlegame_filter(
    records: list[dict[str, object]],
    *,
    min_fullmove: int,
    max_fullmove: int,
    min_remaining_pieces_per_side: int,
) -> tuple[list[dict[str, object]], list[dict[str, object]], dict[str, int]]:
    """Annotate records with filter results and return the eligible subset."""
    annotated: list[dict[str, object]] = []
    eligible: list[dict[str, object]] = []
    summary: Counter[str] = Counter()

    for record in records:
        reasons = position_skip_reasons(
            record,
            min_fullmove=min_fullmove,
            max_fullmove=max_fullmove,
            min_remaining_pieces_per_side=min_remaining_pieces_per_side,
        )
        annotated_record = dict(record)
        annotated_record["skip_reasons"] = "|".join(reasons)
        annotated_record["eligible_middlegame"] = not reasons
        annotated.append(annotated_record)

        if reasons:
            for reason in reasons:
                summary[reason] += 1
        else:
            eligible.append(annotated_record)
            summary["eligible_middlegame"] += 1

    summary["total_positions"] = len(records)
    return annotated, eligible, dict(summary)
