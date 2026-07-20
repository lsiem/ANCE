"""On-disk dense float32 NPZ shards for training (Claude's discretion)."""

from __future__ import annotations

from pathlib import Path

import numpy as np
import torch
from torch.utils.data import Dataset

from training.data.features import encode_position
from training.progress import progress_bar


def build_shard(samples: list[dict], out_path: str) -> None:
    stm_rows: list[np.ndarray] = []
    opp_rows: list[np.ndarray] = []
    cp_rows: list[float] = []
    game_result_rows: list[float] = []
    has_result_rows: list[bool] = []

    for sample in progress_bar(samples, desc=f"shard {Path(out_path).name}", unit="pos"):
        stm, opp = encode_position(sample["fen"])
        stm_rows.append(stm)
        opp_rows.append(opp)
        cp_rows.append(float(sample["cp"]))
        game_result = sample.get("game_result")
        if game_result is None:
            game_result_rows.append(float("nan"))
            has_result_rows.append(False)
        else:
            game_result_rows.append(float(game_result))
            has_result_rows.append(True)

    np.savez(
        out_path,
        stm_features=np.stack(stm_rows).astype(np.float32),
        opp_features=np.stack(opp_rows).astype(np.float32),
        cp=np.array(cp_rows, dtype=np.float32),
        game_result=np.array(game_result_rows, dtype=np.float32),
        has_result=np.array(has_result_rows, dtype=np.bool_),
    )


class ShardDataset(Dataset):
    def __init__(
        self,
        shard_path: str,
        *,
        random_fen_skipping: int = 0,
        seed: int | None = None,
    ) -> None:
        data = np.load(Path(shard_path))
        self._stm = data["stm_features"]
        self._opp = data["opp_features"]
        self._cp = data["cp"]
        self._game_result = data["game_result"]
        self._has_result = data["has_result"]
        # nnue-pytorch: skip probability = N / (N + 1)
        self._skip_n = max(0, int(random_fen_skipping))
        self._rng = np.random.default_rng(seed)

    def __len__(self) -> int:
        return int(self._stm.shape[0])

    def _maybe_skip_index(self, idx: int) -> int:
        if self._skip_n <= 0:
            return idx
        # Resample until kept (bounded attempts to avoid infinite loops).
        n = len(self)
        for _ in range(32):
            # Keep with probability 1/(N+1)
            if self._rng.random() < 1.0 / (self._skip_n + 1):
                return idx
            idx = int(self._rng.integers(0, n))
        return idx

    def __getitem__(
        self, idx: int
    ) -> tuple[torch.Tensor, torch.Tensor, torch.Tensor, torch.Tensor, torch.Tensor]:
        idx = self._maybe_skip_index(idx)
        return (
            torch.from_numpy(self._stm[idx].copy()),
            torch.from_numpy(self._opp[idx].copy()),
            torch.as_tensor(self._cp[idx], dtype=torch.float32),
            torch.as_tensor(self._game_result[idx], dtype=torch.float32),
            torch.as_tensor(float(self._has_result[idx]), dtype=torch.float32),
        )
