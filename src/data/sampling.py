"""Sampling helpers for reproducible Lichess subsets."""

from __future__ import annotations

import math
import re
from dataclasses import dataclass


HEADER_RE = re.compile(r'^\[(?P<name>[A-Za-z0-9_]+) "(?P<value>.*)"\]$', re.MULTILINE)


@dataclass(frozen=True, slots=True)
class GameSample:
    """Lightweight metadata needed for sample selection."""

    game_text: str
    game_id: str
    white: str
    black: str
    white_elo: int | None
    black_elo: int | None
    average_elo: float | None
    event: str
    time_control: str
    result: str


def parse_headers(game_text: str) -> dict[str, str]:
    """Parse PGN headers from a raw game string."""
    return {match.group("name"): match.group("value") for match in HEADER_RE.finditer(game_text)}


def safe_elo(raw_value: str | None) -> int | None:
    """Return a sanitized Elo value when present."""
    if not raw_value:
        return None
    try:
        value = int(raw_value)
    except ValueError:
        return None
    if value <= 0:
        return None
    return value


def game_id_from_site(site: str) -> str | None:
    """Return the Lichess game id from a Site header."""
    if not site:
        return None
    if site.startswith("https://lichess.org/"):
        return site.rsplit("/", 1)[-1]
    return None


def game_sample_from_pgn(game_text: str) -> GameSample | None:
    """Build sample metadata from a raw PGN game string."""
    headers = parse_headers(game_text)
    game_id = game_id_from_site(headers.get("Site", ""))
    if not game_id:
        return None

    white_elo = safe_elo(headers.get("WhiteElo"))
    black_elo = safe_elo(headers.get("BlackElo"))
    average_elo = None
    if white_elo is not None and black_elo is not None:
        average_elo = (white_elo + black_elo) / 2

    return GameSample(
        game_text=game_text,
        game_id=game_id,
        white=headers.get("White", ""),
        black=headers.get("Black", ""),
        white_elo=white_elo,
        black_elo=black_elo,
        average_elo=average_elo,
        event=headers.get("Event", ""),
        time_control=headers.get("TimeControl", ""),
        result=headers.get("Result", ""),
    )


def spread_select(samples: list[GameSample], target_count: int) -> list[GameSample]:
    """Select games spread across the average-Elo range."""
    with_elo = [sample for sample in samples if sample.average_elo is not None]
    if len(with_elo) < target_count:
        raise ValueError(
            f"Need at least {target_count} games with usable Elo data, found {len(with_elo)}."
        )

    ordered = sorted(with_elo, key=lambda sample: (sample.average_elo, sample.game_id))
    if target_count == 1:
        return [ordered[len(ordered) // 2]]

    used: set[int] = set()
    selected: list[GameSample] = []
    for slot in range(target_count):
        anchor = round(slot * (len(ordered) - 1) / (target_count - 1))
        choice = nearest_unused_index(anchor, len(ordered), used)
        used.add(choice)
        selected.append(ordered[choice])
    return selected


def nearest_unused_index(anchor: int, length: int, used: set[int]) -> int:
    """Find the nearest index that has not been selected yet."""
    if anchor not in used:
        return anchor
    for delta in range(1, length):
        left = anchor - delta
        if left >= 0 and left not in used:
            return left
        right = anchor + delta
        if right < length and right not in used:
            return right
    raise ValueError("No unused index remained during spread selection.")


def sample_elo_summary(samples: list[GameSample], *, bucket_count: int = 10) -> dict[str, object]:
    """Summarize average Elo distribution for manifests and reports."""
    values = [sample.average_elo for sample in samples if sample.average_elo is not None]
    if not values:
        return {
            "count_with_average_elo": 0,
            "min_average_elo": None,
            "max_average_elo": None,
            "mean_average_elo": None,
            "bucket_count": bucket_count,
            "buckets": [],
        }

    lower = min(values)
    upper = max(values)
    mean = round(sum(values) / len(values), 2)
    if lower == upper:
        return {
            "count_with_average_elo": len(values),
            "min_average_elo": lower,
            "max_average_elo": upper,
            "mean_average_elo": mean,
            "bucket_count": 1,
            "buckets": [{"label": f"{int(lower)}-{int(upper)}", "count": len(values)}],
        }

    width = math.ceil((upper - lower + 1) / bucket_count)
    bucket_edges: list[tuple[int, int]] = []
    for index in range(bucket_count):
        start = int(lower) + index * width
        end = min(int(upper), start + width - 1)
        bucket_edges.append((start, end))

    counts = [0 for _ in bucket_edges]
    for value in values:
        bucket_index = min(int((value - lower) // width), len(bucket_edges) - 1)
        counts[bucket_index] += 1

    return {
        "count_with_average_elo": len(values),
        "min_average_elo": lower,
        "max_average_elo": upper,
        "mean_average_elo": mean,
        "bucket_count": len(bucket_edges),
        "buckets": [
            {"label": f"{start}-{end}", "count": count}
            for (start, end), count in zip(bucket_edges, counts, strict=True)
        ],
    }
