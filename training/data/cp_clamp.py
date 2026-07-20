"""Soft-clamp training centipawn targets before shards (Phase 6)."""

from __future__ import annotations

DEFAULT_CP_CLAMP = 10_000
_MATE_SCORE = 100_000


def clamp_training_cp(cp: float, limit: float = DEFAULT_CP_CLAMP) -> float:
    """Clamp extreme / mate-mapped cp into a trainable range."""
    if limit <= 0:
        raise ValueError(f"limit must be positive, got {limit}")
    return float(max(-limit, min(limit, cp)))


def cp_from_label(
    label: dict,
    *,
    mate_score: int = _MATE_SCORE,
    clamp_limit: float = DEFAULT_CP_CLAMP,
) -> float | None:
    """Map SF/HF {cp|mate} → STM cp, then soft-clamp."""
    if label.get("cp") is not None:
        return clamp_training_cp(float(label["cp"]), clamp_limit)
    mate = label.get("mate")
    if mate is None:
        return None
    mate_n = int(mate)
    if mate_n > 0:
        raw = float(mate_score - mate_n)
    else:
        raw = float(-mate_score - mate_n)
    return clamp_training_cp(raw, clamp_limit)
