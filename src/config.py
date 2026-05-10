"""Configuration objects for the experiment scaffold."""

from dataclasses import dataclass, field


@dataclass(slots=True)
class PositionFilterConfig:
    min_fullmove: int = 10
    max_fullmove: int = 30
    min_remaining_pieces_per_side: int = 8


@dataclass(slots=True)
class ComplexityConfig:
    min_move_probability: float = 0.10
    expansion_plies: int = 3
    high_complexity_threshold: int = 10


@dataclass(slots=True)
class ExperimentConfig:
    game_count: int = 10
    filters: PositionFilterConfig = field(default_factory=PositionFilterConfig)
    complexity: ComplexityConfig = field(default_factory=ComplexityConfig)
