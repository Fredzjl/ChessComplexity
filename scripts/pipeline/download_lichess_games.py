#!/usr/bin/env python3
"""Download a small reproducible sample from a Lichess monthly archive."""

from __future__ import annotations

import argparse
import hashlib
import json
import subprocess
import sys
from datetime import datetime, timezone
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parents[2]
if str(REPO_ROOT) not in sys.path:
    sys.path.insert(0, str(REPO_ROOT))

from src.data import game_sample_from_pgn, sample_elo_summary, spread_select


RESULT_SUFFIXES = ("1-0", "0-1", "1/2-1/2", "*")


def sha256_file(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as handle:
        for chunk in iter(lambda: handle.read(1024 * 1024), b""):
            digest.update(chunk)
    return digest.hexdigest()


def extract_complete_games(archive_path: Path, target_games: int) -> list[str]:
    proc = subprocess.Popen(
        ["zstdcat", str(archive_path)],
        stdout=subprocess.PIPE,
        stderr=subprocess.DEVNULL,
        text=True,
        encoding="utf-8",
        errors="replace",
    )

    assert proc.stdout is not None
    games: list[str] = []
    current: list[str] = []

    try:
        for line in proc.stdout:
            current.append(line)
            stripped = line.strip()
            if stripped == "" and len(current) > 1:
                previous = current[-2].strip()
                if previous.endswith(RESULT_SUFFIXES):
                    games.append("".join(current).strip() + "\n")
                    current = []
                    if len(games) >= target_games:
                        break
    finally:
        proc.kill()
        proc.wait()

    return games


def select_games(
    games: list[str],
    *,
    sampling_mode: str,
    target_games: int,
) -> tuple[list[str], dict[str, object]]:
    """Select the requested subset and return manifest-side metadata."""
    candidate_samples = [sample for game_text in games if (sample := game_sample_from_pgn(game_text)) is not None]
    if sampling_mode == "first_n":
        selected_samples = candidate_samples[:target_games]
    elif sampling_mode == "avg_elo_spread":
        selected_samples = spread_select(candidate_samples, target_games)
    else:  # pragma: no cover - guarded by argparse choices
        raise ValueError(f"Unsupported sampling mode: {sampling_mode}")

    if len(selected_samples) < target_games:
        raise RuntimeError(
            f"Sampling mode {sampling_mode} only yielded {len(selected_samples)} games, expected {target_games}."
        )

    return [sample.game_text for sample in selected_samples], {
        "sampling_mode": sampling_mode,
        "candidate_game_count": len(candidate_samples),
        "selected_game_ids": [sample.game_id for sample in selected_samples],
        "selected_elo_summary": sample_elo_summary(selected_samples),
        "candidate_elo_summary": sample_elo_summary(candidate_samples),
    }


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument(
        "--source-url",
        default="https://database.lichess.org/standard/lichess_db_standard_rated_2026-04.pgn.zst",
    )
    parser.add_argument("--target-games", type=int, default=10)
    parser.add_argument("--candidate-games", type=int, default=300)
    parser.add_argument("--initial-bytes", type=int, default=5 * 1024 * 1024)
    parser.add_argument("--max-bytes", type=int, default=80 * 1024 * 1024)
    parser.add_argument(
        "--sampling-mode",
        default="first_n",
        choices=["first_n", "avg_elo_spread"],
    )
    parser.add_argument("--raw-output", default="data/raw/lichess_sample_10_games.pgn")
    parser.add_argument("--archive-output", default="data/raw/lichess_sample_10_games.partial.pgn.zst")
    parser.add_argument("--manifest-output", default="data/manifests/lichess_sample_10_games.json")
    args = parser.parse_args()

    raw_output = Path(args.raw_output)
    archive_output = Path(args.archive_output)
    manifest_output = Path(args.manifest_output)

    raw_output.parent.mkdir(parents=True, exist_ok=True)
    archive_output.parent.mkdir(parents=True, exist_ok=True)
    manifest_output.parent.mkdir(parents=True, exist_ok=True)

    byte_count = args.initial_bytes
    games: list[str] = []

    while byte_count <= args.max_bytes:
        end_byte = byte_count - 1
        subprocess.run(
            [
                "curl",
                "-L",
                "-r",
                f"0-{end_byte}",
                args.source_url,
                "-o",
                str(archive_output),
            ],
            check=True,
        )
        target_extract_count = max(args.target_games, args.candidate_games)
        games = extract_complete_games(archive_output, target_extract_count)
        if len(games) >= target_extract_count:
            break
        byte_count *= 2

    if len(games) < args.target_games:
        raise RuntimeError(
            f"Could only extract {len(games)} complete games after downloading {byte_count // 2} bytes."
        )

    selected_games, selection_metadata = select_games(
        games,
        sampling_mode=args.sampling_mode,
        target_games=args.target_games,
    )
    raw_output.write_text("\n\n".join(game.strip() for game in selected_games) + "\n", encoding="utf-8")

    game_ids = selection_metadata["selected_game_ids"]

    manifest = {
        "source_url": args.source_url,
        "archive_output": str(archive_output),
        "raw_output": str(raw_output),
        "target_games": args.target_games,
        "downloaded_bytes": byte_count,
        "byte_range": f"0-{byte_count - 1}",
        "archive_sha256": sha256_file(archive_output),
        "raw_sha256": sha256_file(raw_output),
        "extraction_timestamp_utc": datetime.now(timezone.utc).isoformat(),
        "sampling_mode": args.sampling_mode,
        "candidate_games_requested": args.candidate_games,
        "candidate_games_extracted": len(games),
        "candidate_elo_summary": selection_metadata["candidate_elo_summary"],
        "selected_elo_summary": selection_metadata["selected_elo_summary"],
        "game_ids": game_ids,
    }
    manifest_output.write_text(json.dumps(manifest, indent=2) + "\n", encoding="utf-8")

    print(f"Saved raw sample to {raw_output}")
    print(f"Saved archive slice to {archive_output}")
    print(f"Saved manifest to {manifest_output}")
    print(f"Game count: {len(selected_games)}")
    print("Game IDs:")
    for game_id in game_ids:
        print(game_id)


if __name__ == "__main__":
    main()
