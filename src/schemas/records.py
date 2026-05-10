"""Data structures for experiment records."""

from dataclasses import dataclass


@dataclass(slots=True)
class PositionRecord:
    position_id: str
    game_id: str
    ply_index: int
    fullmove_number: int
    fen: str
    remaining_white_pieces: int
    remaining_black_pieces: int


@dataclass(slots=True)
class PolicySnapshot:
    position_id: str
    fen: str
    model_name: str
    ply_depth: int


@dataclass(slots=True)
class ComplexityResult:
    position_id: str
    complexity_score: int
    high_complexity: bool
