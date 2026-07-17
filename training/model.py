"""The (768→256)×2→1 NNUE architecture (D-06, TRN-03).

All tensor operations stay at single-precision floating point throughout,
consistent with the project's MPS constraints.
"""

from __future__ import annotations

import torch
from torch import nn

NUM_FEATURES = 768
HIDDEN = 256


class ClippedReLU(nn.Module):
    def forward(self, x: torch.Tensor) -> torch.Tensor:
        return torch.clamp(x, 0.0, 1.0)


class NNUE(nn.Module):
    def __init__(self, num_features: int = NUM_FEATURES, hidden: int = HIDDEN) -> None:
        super().__init__()
        self.ft = nn.Linear(num_features, hidden)
        self.clipped_relu = ClippedReLU()
        self.output = nn.Linear(hidden * 2, 1)

    def forward(
        self, stm_features: torch.Tensor, opp_features: torch.Tensor
    ) -> torch.Tensor:
        stm_acc = self.clipped_relu(self.ft(stm_features))
        opp_acc = self.clipped_relu(self.ft(opp_features))
        combined = torch.cat([stm_acc, opp_acc], dim=1)
        return self.output(combined).squeeze(-1)
