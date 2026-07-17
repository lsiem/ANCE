"""Empirical K-fit calibration for sigmoid-WDL training (D-04, D-05)."""

from __future__ import annotations

import numpy as np
from scipy.optimize import curve_fit


def sigmoid(cp: np.ndarray, k: float) -> np.ndarray:
    return 1.0 / (1.0 + np.exp(-cp / k))


def fit_k(
    cp_values: np.ndarray,
    game_results: np.ndarray,
    k0: float = 400.0,
) -> float:
    (k_fit,), _ = curve_fit(sigmoid, cp_values, game_results, p0=[k0])
    return float(k_fit)


def fit_k_from_samples(
    samples: list[dict],
    k0: float = 400.0,
    min_result_rows: int = 30,
) -> float:
    result_rows = [
        sample
        for sample in samples
        if sample.get("game_result") is not None
    ]
    if len(result_rows) < min_result_rows:
        raise ValueError(
            f"need at least {min_result_rows} rows with game_result, "
            f"got {len(result_rows)}"
        )

    cp_values = np.array([row["cp"] for row in result_rows], dtype=np.float64)
    game_results = np.array(
        [row["game_result"] for row in result_rows], dtype=np.float64
    )
    return fit_k(cp_values, game_results, k0=k0)
