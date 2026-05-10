"""Local Maia-2 adapter used by the experiment pipeline."""

from __future__ import annotations

from dataclasses import dataclass, field
from pathlib import Path

import chess
import torch


def resolve_device(requested_device: str) -> str:
    """Resolve a user-facing device setting to an actual local device."""
    if requested_device == "mps":
        return "mps" if torch.backends.mps.is_available() else "cpu"
    if requested_device == "cpu":
        return "cpu"
    if requested_device == "auto":
        return "mps" if torch.backends.mps.is_available() else "cpu"
    raise ValueError(f"Unsupported device setting: {requested_device}")


def sorted_policy_items(move_probs: dict[str, float]) -> list[tuple[str, float]]:
    """Return policy items sorted by descending probability."""
    return sorted(move_probs.items(), key=lambda item: item[1], reverse=True)


def qualifying_policy_items(
    move_probs: dict[str, float],
    *,
    min_probability: float,
) -> list[tuple[str, float]]:
    """Return moves that satisfy the expansion threshold."""
    return [
        (move, probability)
        for move, probability in sorted_policy_items(move_probs)
        if probability >= min_probability
    ]


@dataclass(slots=True)
class Maia2Adapter:
    """Local interface for Maia-2 policy inference."""

    model_type: str = "rapid"
    requested_device: str = "auto"
    save_root: str | Path = "models/maia2"
    model: object | None = field(default=None, init=False)
    prepared: object | None = field(default=None, init=False)
    cpu_fallback_model: object | None = field(default=None, init=False)
    cpu_fallback_prepared: object | None = field(default=None, init=False)
    actual_device: str = field(default="cpu", init=False)

    def load(self) -> None:
        """Load Maia-2 weights and preprocessing state."""
        from maia2.inference import prepare
        from maia2.model import from_pretrained

        self.actual_device = resolve_device(self.requested_device)
        self.model = from_pretrained(self.model_type, "cpu", save_root=str(self.save_root))
        if self.actual_device == "mps":
            self.model = self.model.to("mps")
        self.prepared = prepare()

    def load_cpu_fallback(self) -> None:
        """Load a CPU copy for backend-specific fallback inference."""
        from maia2.inference import prepare
        from maia2.model import from_pretrained

        if self.cpu_fallback_model is not None and self.cpu_fallback_prepared is not None:
            return

        self.cpu_fallback_model = from_pretrained(self.model_type, "cpu", save_root=str(self.save_root))
        self.cpu_fallback_prepared = prepare()

    def predict_policy(
        self,
        fen: str,
        *,
        elo_self: int,
        elo_oppo: int,
    ) -> dict[str, object]:
        """Run Maia-2 on one FEN and return the full policy result."""
        from maia2.inference import inference_each

        if self.model is None or self.prepared is None:
            self.load()

        board = chess.Board(fen)
        inference_device = self.actual_device
        try:
            move_probs, win_prob = inference_each(self.model, self.prepared, fen, elo_self, elo_oppo)
        except Exception:
            if self.actual_device != "mps":
                raise
            self.load_cpu_fallback()
            move_probs, win_prob = inference_each(
                self.cpu_fallback_model,
                self.cpu_fallback_prepared,
                fen,
                elo_self,
                elo_oppo,
            )
            inference_device = "cpu_fallback"
        return {
            "fen": fen,
            "side_to_move": "white" if board.turn == chess.WHITE else "black",
            "move_probs": dict(sorted_policy_items(move_probs)),
            "win_prob": win_prob,
            "move_count": len(move_probs),
            "model_name": "maia2",
            "model_version": "0.9",
            "model_type": self.model_type,
            "requested_device": self.requested_device,
            "actual_device": inference_device,
        }
