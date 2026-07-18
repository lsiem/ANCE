"""NNUE evaluation package (EVAL-03).

`ance.eval.nnue.eval` provides `NnueEval`, the zero-torch `(768→256)×2→1`
evaluator wired behind the `Evaluator` Protocol seam. Weights load via
`nnue_format.io.load_net`; feature encoding mirrors
`training/data/features.py` bit-for-bit.
"""

from __future__ import annotations

from ance.eval.nnue.eval import NnueEval

__all__ = ["NnueEval"]
