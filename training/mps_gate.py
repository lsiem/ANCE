"""MPS availability gate and CPU-vs-MPS numeric parity check (D-09, TRN-05)."""

from __future__ import annotations

from collections.abc import Callable

import torch
from torch import nn

# Known macOS-major regression: is_built() True but is_available() False.
# https://github.com/pytorch/pytorch/issues/167679
# https://github.com/pytorch/pytorch/issues/177819
_MPS_REGRESSION_ISSUES = ("167679", "177819")


def _default_sanity_model() -> nn.Module:
    return nn.Sequential(
        nn.Linear(768, 8),
        nn.ReLU(),
        nn.Linear(8, 1),
    )


def select_device() -> str:
    """Probe MPS availability and return ``\"mps\"`` or ``\"cpu\"``."""
    built = torch.backends.mps.is_built()
    available = torch.backends.mps.is_available()
    print(
        f"torch={torch.__version__} mps.is_built={built} "
        f"mps.is_available={available}"
    )
    if built and not available:
        issue_refs = ", ".join(f"#{num}" for num in _MPS_REGRESSION_ISSUES)
        print(
            "WARNING: MPS built but unavailable — known regression on some macOS "
            f"majors (see github.com/pytorch/pytorch/issues/{issue_refs}). "
            "Falling back to CPU per D-09."
        )
    return "mps" if available else "cpu"


def cpu_vs_mps_parity_check(
    device: str,
    model_factory: Callable[[], nn.Module] | None = None,
    atol: float = 1e-4,
) -> None:
    """Run one forward+backward step on CPU and ``device``, assert loss parity."""
    if device == "cpu":
        print("Device is CPU; parity check is a no-op (nothing to compare against).")
        return

    factory = model_factory or _default_sanity_model
    torch.manual_seed(0)
    features = torch.randn(4, 768, dtype=torch.float32)
    targets = torch.randn(4, dtype=torch.float32)

    def one_step(dev: str) -> torch.Tensor:
        torch.manual_seed(0)
        model = factory().to(dev)
        output = model(features.to(dev)).squeeze(-1)
        loss = ((output - targets.to(dev)) ** 2).mean()
        loss.backward()
        return loss.detach().cpu()

    cpu_loss = one_step("cpu")
    device_loss = one_step(device)
    if not torch.allclose(cpu_loss, device_loss, atol=atol):
        raise AssertionError(
            f"CPU/MPS numeric mismatch: {cpu_loss.item()} vs {device_loss.item()} "
            f"(atol={atol}) — suspect an MPS kernel bug; do not trust MPS for the "
            "real run"
        )
    print(f"CPU/MPS parity OK: {cpu_loss.item():.6f} vs {device_loss.item():.6f}")
