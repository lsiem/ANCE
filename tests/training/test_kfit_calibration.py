"""Tests for K-fit calibration."""

from __future__ import annotations

import numpy as np

from training.data.kfit import fit_k, fit_k_from_samples, sigmoid


def test_fit_k_recovers_known_k() -> None:
    rng = np.random.default_rng(0)
    cp_values = np.linspace(-800, 800, 500)
    game_results = sigmoid(cp_values, k=387.0) + rng.normal(0, 0.01, size=500)
    recovered = fit_k(cp_values, game_results)
    assert abs(recovered - 387.0) <= 15


def test_fit_k_from_samples_excludes_eval_only_rows() -> None:
    rng = np.random.default_rng(1)
    known_k = 387.0
    with_result = []
    for index in range(60):
        cp = float(rng.integers(-600, 600))
        with_result.append(
            {
                "fen": f"fen-{index}",
                "cp": cp,
                "game_result": float(sigmoid(np.array([cp]), known_k)[0]),
                "game_id": f"g-{index // 10}",
            }
        )

    eval_only = [
        {
            "fen": f"bad-{index}",
            "cp": 99999.0,
            "game_result": None,
            "game_id": f"bad-{index}",
        }
        for index in range(20)
    ]

    recovered = fit_k_from_samples(with_result + eval_only)
    assert abs(recovered - known_k) <= 15
