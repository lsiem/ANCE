"""NNUE weights contract constants (D-07, TRN-04).

``ARCH_ID``, ``FEATURE_SET``, and ``EXPECTED_SHAPES`` are defined once here
and imported everywhere — same convention as ``ance.eval.base.MATE``.

``ft.weight`` and ``out.weight`` are stored **already transposed** to
``(in_features, out_features)`` — the opposite orientation of PyTorch
``nn.Linear``'s native ``(out_features, in_features)`` ``state_dict``
layout — so a zero-torch numpy loader can do a direct
``features @ weight + bias`` matmul at inference time with no transpose
step. ``training/export.py`` (Plan 04-02) performs that transpose before
calling ``save_net``; this module only documents and validates the
resulting on-disk shape contract.
"""

from __future__ import annotations

ARCH_ID = "768x2-256-1"
FEATURE_SET = "board768"

EXPECTED_SHAPES: dict[str, tuple[int, ...]] = {
    "ft.weight": (768, 256),
    "ft.bias": (256,),
    "out.weight": (512, 1),
    "out.bias": (1,),
}
